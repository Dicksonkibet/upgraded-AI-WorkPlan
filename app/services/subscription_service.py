import requests
import base64
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import User
from app.models.subscription import Subscription, Payment
from app.services.settings_service import settings_service


class MPesaService:
    """Safaricom Daraja API — STK Push integration."""

    def _base_url(self):
        env = settings_service.get('mpesa_env')
        if env == 'production':
            return 'https://api.safaricom.co.ke'
        return 'https://sandbox.safaricom.co.ke'

    def _get_token(self):
        # Consumer key/secret are credentials — kept in .env only, never admin-editable.
        key    = current_app.config['MPESA_CONSUMER_KEY']
        secret = current_app.config['MPESA_CONSUMER_SECRET']
        creds  = base64.b64encode(f'{key}:{secret}'.encode()).decode()
        r = requests.get(
            f'{self._base_url()}/oauth/v1/generate?grant_type=client_credentials',
            headers={'Authorization': f'Basic {creds}'},
            timeout=10
        )
        r.raise_for_status()
        return r.json()['access_token']

    def _password(self, timestamp):
        shortcode = settings_service.get('mpesa_shortcode')
        # Passkey is a credential — kept in .env only, never admin-editable.
        passkey   = current_app.config['MPESA_PASSKEY']
        raw = f'{shortcode}{passkey}{timestamp}'
        return base64.b64encode(raw.encode()).decode()

    def initiate_stk_push(self, phone: str, amount: int, billing_cycle: str, user_id: int):
        """Initiate M-Pesa STK Push. Returns (checkout_id, error)."""
        try:
            token     = self._get_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            shortcode = settings_service.get('mpesa_shortcode')
            callback  = settings_service.get('mpesa_callback_url')

            # Normalize phone: 0712... → 254712...
            phone = phone.strip().replace(' ', '').replace('-', '')
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]

            payload = {
                'BusinessShortCode': shortcode,
                'Password':          self._password(timestamp),
                'Timestamp':         timestamp,
                'TransactionType':   'CustomerPayBillOnline',
                'Amount':            amount,
                'PartyA':            phone,
                'PartyB':            shortcode,
                'PhoneNumber':       phone,
                'CallBackURL':       callback,
                'AccountReference':  f'WorkPro-{user_id}',
                'TransactionDesc':   f'WorkPro Pro {billing_cycle} subscription',
            }

            r = requests.post(
                f'{self._base_url()}/mpesa/stkpush/v1/processrequest',
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type':  'application/json',
                },
                timeout=15
            )
            data = r.json()

            if data.get('ResponseCode') == '0':
                checkout_id = data['CheckoutRequestID']
                return checkout_id, None
            else:
                return None, data.get('errorMessage', 'STK Push failed')

        except Exception as e:
            current_app.logger.error(f'M-Pesa STK error: {e}')
            return None, f'Payment service error: {str(e)}'

    def query_stk_status(self, checkout_id: str):
        """Query STK push status. Returns (status_dict, error)."""
        try:
            token     = self._get_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            shortcode = settings_service.get('mpesa_shortcode')

            payload = {
                'BusinessShortCode': shortcode,
                'Password':          self._password(timestamp),
                'Timestamp':         timestamp,
                'CheckoutRequestID': checkout_id,
            }

            r = requests.post(
                f'{self._base_url()}/mpesa/stkpushquery/v1/query',
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type':  'application/json',
                },
                timeout=10
            )
            return r.json(), None
        except Exception as e:
            return None, str(e)


class SubscriptionService:

    def get_or_create(self, user_id: int) -> Subscription:
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if not sub:
            sub = Subscription(user_id=user_id, plan='free', status='active')
            db.session.add(sub)
            db.session.commit()
        return sub

    def get_billing_history(self, user_id: int):
        return Payment.query.filter_by(user_id=user_id)\
            .order_by(Payment.created_at.desc()).limit(20).all()

    def initiate_upgrade(self, user_id: int, phone: str, billing_cycle: str,
                         promo_discount: float = 0):
        """Start M-Pesa payment and create pending payment record."""
        cycle   = billing_cycle.lower()
        amount  = (
            settings_service.get('pro_monthly_price') if cycle == 'monthly'
            else settings_service.get('pro_annual_price')
        )
        # Apply discount
        final_amount = max(1, int(amount) - int(promo_discount))

        mpesa        = MPesaService()
        checkout_id, err = mpesa.initiate_stk_push(phone, final_amount, cycle, user_id)
        if err:
            return None, err

        sub = self.get_or_create(user_id)

        payment = Payment(
            subscription_id   = sub.id,
            user_id           = user_id,
            amount            = final_amount,
            currency          = 'KES',
            status            = 'pending',
            mpesa_checkout_id = checkout_id,
            phone_number      = phone,
            billing_cycle     = cycle,
        )
        db.session.add(payment)
        db.session.commit()
        return {'checkout_id': checkout_id, 'amount': final_amount, 'payment_id': payment.id}, None

    def confirm_payment(self, checkout_id: str, receipt: str):
        """Called by M-Pesa callback or manual confirmation."""
        payment = Payment.query.filter_by(mpesa_checkout_id=checkout_id).first()
        if not payment:
            return False

        payment.status        = 'completed'
        payment.mpesa_receipt = receipt
        payment.completed_at  = datetime.utcnow()

        # Activate/extend subscription
        sub = payment.subscription
        sub.plan          = 'pro'
        sub.status        = 'active'
        sub.billing_cycle = payment.billing_cycle
        sub.amount_paid   = payment.amount
        sub.started_at    = datetime.utcnow()

        if payment.billing_cycle == 'annual':
            sub.expires_at = datetime.utcnow() + timedelta(days=365)
        else:
            sub.expires_at = datetime.utcnow() + timedelta(days=30)

        db.session.commit()

        # Trigger referral commission
        try:
            from app.services.referral_service import referral_service
            referral_service.process_commission(payment)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Commission processing error: %s', e)

        # Apply pending promo usage if any
        try:
            from flask import session
            promo_key = f'pending_promo_{payment.id}'
            promo_data = session.pop(promo_key, None)
            if promo_data:
                from app.services.promo_service import promo_service
                from app.models.team import PromoCode
                p = PromoCode.query.get(promo_data['promo_id'])
                if p:
                    promo_service.apply(p, payment.user_id, payment.id,
                                        promo_data['discount'])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Promo apply error: %s', e)

        return True

    def check_and_confirm(self, payment_id: int):
        """Poll M-Pesa to check payment status (for polling endpoint)."""
        payment = Payment.query.get(payment_id)
        if not payment:
            return 'not_found'
        if payment.status == 'completed':
            return 'completed'

        mpesa  = MPesaService()
        result, err = mpesa.query_stk_status(payment.mpesa_checkout_id)
        if err:
            return 'error'

        code = str(result.get('ResultCode', ''))
        if code == '0':
            receipt = result.get('MpesaReceiptNumber', payment.mpesa_checkout_id)
            self.confirm_payment(payment.mpesa_checkout_id, receipt)
            return 'completed'
        elif code == '1032':
            payment.status = 'cancelled'
            db.session.commit()
            return 'cancelled'
        elif code != '':
            payment.status = 'failed'
            db.session.commit()
            return 'failed'

        return 'pending'

    def cancel_subscription(self, user_id: int):
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if sub and sub.is_pro:
            sub.status       = 'cancelled'
            sub.cancelled_at = datetime.utcnow()
            db.session.commit()
            return True
        return False


subscription_service = SubscriptionService()
