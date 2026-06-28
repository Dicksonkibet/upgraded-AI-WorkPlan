from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.services.subscription_service import subscription_service
from app.services.settings_service import settings_service
from app.utils.decorators import get_visible_menus

sub_bp = Blueprint('subscription', __name__)


@sub_bp.route('/')
@login_required
def index():
    sub     = subscription_service.get_or_create(current_user.id)
    history = subscription_service.get_billing_history(current_user.id)
    usage   = current_user.get_usage()
    limits  = current_user.get_limits()
    return render_template('subscription/index.html',
        sub=sub, history=history, usage=usage, limits=limits,
        pro_monthly=settings_service.get('pro_monthly_price'),
        pro_annual=settings_service.get('pro_annual_price'),
        menus=get_visible_menus(current_user))


@sub_bp.route('/validate-promo', methods=['POST'])
@login_required
def validate_promo():
    """AJAX: validate a promo code and return discount info."""
    from app.services.promo_service import promo_service
    data = request.get_json()
    code = (data or {}).get('code', '').strip()
    amount = float((data or {}).get('amount', 0))
    if not code:
        return jsonify({'error': 'Enter a promo code.'}), 400
    promo, discount, err = promo_service.validate(code, current_user.id, amount)
    if err:
        return jsonify({'error': err}), 400
    return jsonify({
        'valid': True,
        'discount': discount,
        'final_amount': max(0, amount - discount),
        'description': promo.description or '',
        'discount_type': promo.discount_type,
        'discount_value': promo.discount_value,
    })


@sub_bp.route('/initiate', methods=['POST'])
@login_required
def initiate():
    from app.services.promo_service import promo_service
    data   = request.get_json()
    phone  = data.get('phone', '').strip()
    cycle  = data.get('billing_cycle', 'monthly')
    promo_code_str = data.get('promo_code', '').strip()

    if not phone:
        return jsonify({'error': 'Phone number is required.'}), 400

    # Validate promo if provided
    promo_obj = None
    promo_discount = 0
    if promo_code_str:
        base_amount = float(
            settings_service.get('pro_monthly_price') if cycle == 'monthly'
            else settings_service.get('pro_annual_price')
        )
        promo_obj, promo_discount, promo_err = promo_service.validate(
            promo_code_str, current_user.id, base_amount
        )
        if promo_err:
            return jsonify({'error': f'Promo: {promo_err}'}), 400

    result, err = subscription_service.initiate_upgrade(
        current_user.id, phone, cycle,
        promo_discount=promo_discount,
    )
    if err:
        return jsonify({'error': err}), 400

    # Store promo reference so it can be applied on payment confirm
    if promo_obj and result:
        from app import db
        from flask import session
        session[f'pending_promo_{result["payment_id"]}'] = {
            'promo_id': promo_obj.id,
            'discount': promo_discount,
        }

    return jsonify({'success': True, **result})


@sub_bp.route('/poll/<int:payment_id>', methods=['GET'])
@login_required
def poll_payment(payment_id):
    status = subscription_service.check_and_confirm(payment_id)
    return jsonify({'status': status})


@sub_bp.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    """M-Pesa webhook callback."""
    try:
        data    = request.get_json(force=True)
        body    = data.get('Body', {})
        stk     = body.get('stkCallback', {})
        code    = stk.get('ResultCode')
        cid     = stk.get('CheckoutRequestID')

        if str(code) == '0':
            items   = {i['Name']: i['Value'] for i in stk.get('CallbackMetadata', {}).get('Item', [])}
            receipt = items.get('MpesaReceiptNumber', cid)
            subscription_service.confirm_payment(cid, receipt)

        return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})
    except Exception as e:
        return jsonify({'ResultCode': 1, 'ResultDesc': str(e)}), 500


@sub_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    ok = subscription_service.cancel_subscription(current_user.id)
    if ok:
        flash('Your subscription has been cancelled. You can still use Pro features until your period ends.', 'info')
    else:
        flash('No active subscription to cancel.', 'warning')
    return redirect(url_for('subscription.index'))
