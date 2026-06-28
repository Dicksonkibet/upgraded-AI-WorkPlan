from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.services import auth_service
from app.models.user import User
from flask import current_app

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    error = None
    unverified_email = None
    if request.method == 'POST':
        user, err, code = auth_service.login(
            request.form.get('email', ''),
            request.form.get('password', '')
        )
        if err:
            error = err
            if code == 'unverified':
                unverified_email = request.form.get('email', '')
        else:
            login_user(user, remember=request.form.get('remember') == 'on')
            if user.is_admin():
                session['admin_session_token'] = auth_service.start_session(user)
            return redirect(request.args.get('next') or url_for('dashboard.index'))
    return render_template('auth/login.html', error=error, unverified_email=unverified_email)


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email', '')
    auth_service.resend_verification(email)
    # Always show success to avoid revealing account existence
    flash('If that email is registered and unverified, a new verification link has been sent.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Capture ref code in session so it survives the POST
    ref_code = request.args.get('ref', '').strip()
    if ref_code:
        session['ref_code'] = ref_code

    error = None

    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirm_password'):
            error = 'Passwords do not match.'
        else:
            user, err = auth_service.register({
                'first_name': request.form.get('first_name', ''),
                'last_name':  request.form.get('last_name', ''),
                'email':      request.form.get('email', ''),
                'password':   request.form.get('password', ''),
            })

            if err:
                error = err
            else:
                current_app.logger.info('Registration successful for %s', request.form.get('email', ''))
                # Track referral signup if ref code provided
                ref_code = request.form.get('ref_code', '').strip() or session.pop('ref_code', None)
                if ref_code and user:
                    try:
                        from app.services.referral_service import referral_service
                        referral_service.record_signup(ref_code, user.id)
                    except Exception as e:
                        current_app.logger.warning('Referral tracking error: %s', e)
                flash('Account created! Please check your email to verify.', 'success')
                return redirect(url_for('auth.login'))

    return render_template('auth/register.html', error=error, ref_code=session.get('ref_code', ''))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    sent = False
    if request.method == 'POST':
        auth_service.send_reset_email(request.form.get('email', ''))
        sent = True
    return render_template('auth/forgot_password.html', sent=sent)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # ── Validate token before showing the form at all ─────────────
    # This runs on both GET and POST so a used/expired token is always
    # caught immediately and the user is sent to login with a clear message.
    user = User.verify_reset_token(token)
    if not user:
        current_app.logger.warning('Invalid or expired password reset token used.')
        flash('This password reset link is invalid or has already been used. Please request a new one.', 'danger')
        return redirect(url_for('auth.login'))

    error = None
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if pwd != request.form.get('confirm_password', ''):
            error = 'Passwords do not match.'
        elif len(pwd) < 8:
            error = 'Password must be at least 8 characters.'
        else:
            auth_service.reset_password(token, pwd)
            current_app.logger.info('Password reset successfully for user %s', user.email)
            flash('Password reset successfully. Please log in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token, error=error)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    if auth_service.verify_email(token):
        flash('Email verified! You can now log in.', 'success')
    else:
        flash('Verification link is invalid or has already been used.', 'danger')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    if current_user.is_admin():
        auth_service.end_session(current_user)
    logout_user()
    return redirect(url_for('landing.index'))