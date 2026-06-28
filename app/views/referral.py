from flask import Blueprint, render_template, request, jsonify, url_for, flash, redirect
from flask_login import login_required, current_user
from app.services.referral_service import referral_service
from app.utils.decorators import admin_required, get_visible_menus

referral_bp = Blueprint('referral', __name__)


@referral_bp.route('/')
@login_required
def index():
    stats = referral_service.get_user_stats(current_user.id)
    ref_url = url_for('auth.register', ref=stats['code'], _external=True)
    return render_template('referral/index.html',
        stats=stats, ref_url=ref_url,
        menus=get_visible_menus(current_user))


@referral_bp.route('/api/stats')
@login_required
def api_stats():
    stats = referral_service.get_user_stats(current_user.id)
    stats['ref_url'] = url_for('auth.register', ref=stats['code'], _external=True)
    return jsonify(stats)


# ── Admin endpoints ────────────────────────────────────────────────────────────

@referral_bp.route('/admin')
@login_required
@admin_required
def admin_commissions():
    commissions = referral_service.get_all_commissions()
    return render_template('referral/admin.html',
        commissions=commissions,
        menus=get_visible_menus(current_user))


@referral_bp.route('/admin/pay/<int:commission_id>', methods=['POST'])
@login_required
@admin_required
def admin_pay(commission_id):
    receipt = request.form.get('receipt', '').strip()
    ok, msg = referral_service.manual_payout(commission_id, receipt or None)
    if ok:
        flash(f'Commission #{commission_id} marked as paid.', 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('referral.admin_commissions'))
