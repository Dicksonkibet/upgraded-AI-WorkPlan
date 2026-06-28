"""
Referral & Commission service.

Commission rate is configurable in admin settings (default 20%).
Auto-payout via M-Pesa B2C when a payment is confirmed.
"""
import requests
import base64
from datetime import datetime
from flask import current_app
from app import db
from app.models.user import User
from app.models.subscription import Payment
from app.models.referral import ReferralCode, ReferralSignup, Commission
from app.services.settings_service import settings_service


class ReferralService:

    # ── Code management ──────────────────────────────────────────────

    def get_or_create_code(self, user_id: int) -> ReferralCode:
        code = ReferralCode.query.filter_by(user_id=user_id).first()
        if not code:
            for _ in range(10):
                candidate = ReferralCode.generate_code()
                if not ReferralCode.query.filter_by(code=candidate).first():
                    code = ReferralCode(user_id=user_id, code=candidate)
                    db.session.add(code)
                    db.session.commit()
                    break
        return code

    def get_code_by_string(self, code_str: str):
        return ReferralCode.query.filter_by(code=code_str.upper()).first()

    # ── Signup tracking ──────────────────────────────────────────────

    def record_signup(self, referral_code_str: str, new_user_id: int):
        """Call right after a new user registers with a ref= code."""
        code = self.get_code_by_string(referral_code_str)
        if not code:
            return
        # Don't allow self-referral
        if code.user_id == new_user_id:
            return
        # Don't double-record
        existing = ReferralSignup.query.filter_by(
            referral_code_id=code.id,
            referred_user_id=new_user_id
        ).first()
        if existing:
            return
        signup = ReferralSignup(
            referral_code_id=code.id,
            referred_user_id=new_user_id,
        )
        db.session.add(signup)
        db.session.commit()

    # ── Commission on payment ─────────────────────────────────────────

    def process_commission(self, payment: Payment):
        """
        Called when a payment is confirmed.
        Looks up whether the paying user was referred, creates a Commission,
        and triggers auto-payout.
        """
        user_id = payment.user_id
        signup  = ReferralSignup.query.filter_by(referred_user_id=user_id, converted=False).first()
        if not signup:
            return   # user wasn't referred, or already rewarded

        rate    = float(settings_service.get('commission_rate') or 20) / 100
        amount  = round(payment.amount * rate, 2)
        code    = signup.referral_code

        commission = Commission(
            referral_code_id = code.id,
            referrer_id      = code.user_id,
            referred_user_id = user_id,
            payment_id       = payment.id,
            amount           = amount,
            rate             = rate * 100,
            status           = 'pending',
        )
        db.session.add(commission)

        # Mark signup as converted
        signup.converted    = True
        signup.converted_at = datetime.utcnow()
        db.session.commit()

        # Attempt auto-payout
        self._auto_payout(commission)

    # ── Auto-payout via M-Pesa B2C ────────────────────────────────────

    def _auto_payout(self, commission: Commission):
        """Send M-Pesa B2C payment to referrer. Falls back to 'pending' on error."""
        referrer = User.query.get(commission.referrer_id)
        if not referrer:
            commission.notes = 'Referrer not found'
            db.session.commit()
            return

        # We store the referrer's payout phone in their profile (phone field)
        phone = getattr(referrer, 'phone', None)
        if not phone:
            commission.notes  = 'No payout phone on file — pending manual payout'
            db.session.commit()
            current_app.logger.info(
                'Commission %d queued (no phone for user %d)', commission.id, referrer.id
            )
            return

        commission.phone_number = phone
        db.session.commit()

        try:
            token     = self._get_token()
            env       = settings_service.get('mpesa_env')
            base_url  = ('https://api.safaricom.co.ke'
                         if env == 'production'
                         else 'https://sandbox.safaricom.co.ke')
            shortcode = settings_service.get('mpesa_shortcode')
            initiator = current_app.config.get('MPESA_INITIATOR_NAME', 'testapi')
            security  = current_app.config.get('MPESA_SECURITY_CREDENTIAL', '')

            # Normalize phone
            phone = phone.strip().replace(' ', '').replace('-', '')
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]

            payload = {
                'InitiatorName':      initiator,
                'SecurityCredential': security,
                'CommandID':          'BusinessPayment',
                'Amount':             int(commission.amount),
                'PartyA':             shortcode,
                'PartyB':             phone,
                'Remarks':            f'WorkPro referral commission #{commission.id}',
                'QueueTimeOutURL':    settings_service.get('mpesa_callback_url') + '/timeout',
                'ResultURL':          settings_service.get('mpesa_callback_url') + '/b2c-result',
                'Occassion':          'Commission',
            }

            r = requests.post(
                f'{base_url}/mpesa/b2c/v1/paymentrequest',
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type':  'application/json',
                },
                timeout=15
            )
            data = r.json()
            if data.get('ResponseCode') == '0':
                commission.status = 'paid'
                commission.paid_at = datetime.utcnow()
                commission.mpesa_receipt = data.get('ConversationID', '')
                commission.notes = 'Auto-paid via B2C'
            else:
                commission.notes = data.get('errorMessage', 'B2C failed — pending manual')
        except Exception as e:
            commission.notes = f'B2C error: {str(e)[:200]} — pending manual'
            current_app.logger.error('B2C payout error for commission %d: %s', commission.id, e)

        db.session.commit()

    def _get_token(self):
        key    = current_app.config['MPESA_CONSUMER_KEY']
        secret = current_app.config['MPESA_CONSUMER_SECRET']
        creds  = base64.b64encode(f'{key}:{secret}'.encode()).decode()
        env    = settings_service.get('mpesa_env')
        base   = ('https://api.safaricom.co.ke'
                  if env == 'production'
                  else 'https://sandbox.safaricom.co.ke')
        r = requests.get(
            f'{base}/oauth/v1/generate?grant_type=client_credentials',
            headers={'Authorization': f'Basic {creds}'},
            timeout=10
        )
        r.raise_for_status()
        return r.json()['access_token']

    # ── Admin: manual payout ──────────────────────────────────────────

    def manual_payout(self, commission_id: int, receipt: str = None):
        c = Commission.query.get(commission_id)
        if not c:
            return False, 'Commission not found'
        c.status   = 'paid'
        c.paid_at  = datetime.utcnow()
        c.notes    = 'Manual payout by admin'
        if receipt:
            c.mpesa_receipt = receipt
        db.session.commit()
        return True, 'Marked as paid'

    # ── Stats ─────────────────────────────────────────────────────────

    def get_user_stats(self, user_id: int):
        code = self.get_or_create_code(user_id)
        return {
            'code':               code.code,
            'total_signups':      code.total_signups,
            'converted_signups':  code.converted_signups,
            'total_earned':       code.total_earned,
            'pending_earnings':   code.pending_earnings,
            'commissions':        [c.to_dict() for c in
                                   code.commissions.order_by(Commission.created_at.desc()).limit(20)],
        }

    def get_all_commissions(self):
        return Commission.query.order_by(Commission.created_at.desc()).all()


referral_service = ReferralService()
