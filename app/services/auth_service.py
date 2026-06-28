from app import db
from app.models import User, Role
from app.interfaces import IAuthService
from flask import current_app
from datetime import datetime
import secrets
import threading
import requests


class AuthService(IAuthService):

    def register(self, data: dict) -> tuple:
        """Returns (user, error_message)"""
        if User.query.filter_by(email=data['email'].lower()).first():
            return None, 'Email already registered.'

        default_role = Role.query.filter_by(is_default=True).first()
        if not default_role:
            default_role = Role.query.filter_by(name='user').first()

        # Public registration is always given the default role ('user').
        # There is no field in the register form/route for role, so this is
        # the only path used here — the admin role can only ever be reached
        # via UserService.change_role(), which itself enforces a single admin.
        user = User(
            first_name  = data['first_name'].strip(),
            last_name   = data['last_name'].strip(),
            email       = data['email'].lower().strip(),
            role_id     = default_role.id if default_role else 1,
            is_verified = False,
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()

        # Send verification email (fire-and-forget, never blocks the request)
        self._send_verification_email(user)

        return user, None

    def login(self, email: str, password: str) -> tuple:
        """Returns (user, error_message, error_code)"""
        user = User.query.filter_by(email=email.lower()).first()
        if not user or not user.check_password(password):
            return None, 'Invalid email or password.', None
        if not user.is_active:
            return None, 'Your account has been deactivated. Contact your administrator.', None
        if not user.is_verified:
            return None, 'Please verify your email before logging in.', 'unverified'
        user.last_login = datetime.utcnow()
        db.session.commit()
        return user, None, None

    def start_session(self, user) -> str:
        """Issue a fresh session token for this user, invalidating any other active
        session for the same account (used to enforce single-admin-login)."""
        token = secrets.token_hex(16)
        user.current_session_token = token
        db.session.commit()
        return token

    def end_session(self, user):
        """Clear the stored session token on logout."""
        user.current_session_token = None
        db.session.commit()

    def send_reset_email(self, email: str) -> bool:
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            return True   # Don't reveal existence
        token = user.get_reset_token()
        url   = f"{current_app.config['FRONTEND_URL']}/auth/reset-password/{token}"
        html = f"""
        <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#f8f9fa;border-radius:12px">
          <h2 style="color:#6c63ff;margin-bottom:8px">WorkPro</h2>
          <h3 style="color:#212529">Reset your password</h3>
          <p style="color:#6c757d">Hi {user.first_name}, click the button below to reset your password. This link expires in 1 hour.</p>
          <a href="{url}" style="display:inline-block;margin:20px 0;padding:12px 28px;background:#6c63ff;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Reset Password</a>
          <p style="color:#adb5bd;font-size:12px">If you didn't request this, ignore this email.</p>
        </div>"""
        self._send_async(
            subject='Reset your WorkPro password',
            recipient=user.email,
            html=html,
        )
        return True
    def reset_password(self, token: str, new_password: str) -> bool:
        user = User.verify_reset_token(token)
        if not user:
            return False
        user.set_password(new_password)
        user.invalidate_reset_token()   # <-- rotate the token nonce so it can't be reused
        db.session.commit()
        return True

    def verify_email(self, token: str) -> bool:
        user = User.verify_email_token(token)
        if not user:
            return False
        user.is_verified = True
        user.invalidate_verify_token()  # <-- rotate so link can't be replayed
        db.session.commit()
        return True

    def resend_verification(self, email: str) -> bool:
        user = User.query.filter_by(email=email.lower()).first()
        if not user or user.is_verified:
            return False
        self._send_verification_email(user)
        return True

    # def verify_email(self, token: str) -> bool:
    #     user = User.verify_email_token(token)
    #     if not user:
    #         return False
    #     user.is_verified = True
    #     db.session.commit()
    #     return True

    def _send_verification_email(self, user):
        token = user.get_verify_token()
        url   = f"{current_app.config['FRONTEND_URL']}/auth/verify-email/{token}"
        html = f"""
        <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#f8f9fa;border-radius:12px">
          <h2 style="color:#6c63ff">WorkPro</h2>
          <h3>Verify your email address</h3>
          <p style="color:#6c757d">Hi {user.first_name}, click below to verify your email.</p>
          <a href="{url}" style="display:inline-block;margin:20px 0;padding:12px 28px;background:#6c63ff;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Verify Email</a>
        </div>"""
        self._send_async(
            subject='Verify your WorkPro email',
            recipient=user.email,
            html=html,
        )

    # ------------------------------------------------------------------
    # Internal mail helpers
    # ------------------------------------------------------------------

    def _send_async(self, subject: str, recipient: str, html: str):
        """
        Send mail via Brevo's HTTP transactional email API (port 443/HTTPS)
        on a background thread.

        We deliberately do NOT use SMTP here. Render's free-tier (and some
        paid) instances block outbound traffic on SMTP ports 25/465/587,
        which previously caused smtplib to hang until gunicorn killed the
        worker (WORKER TIMEOUT -> SIGKILL). Brevo's API is plain HTTPS, the
        same protocol the app already uses for every other outbound call,
        so it is never blocked.

        The background thread + `timeout=` on requests.post still protects
        against Brevo itself being slow/unreachable -- same safety net as
        before, just pointed at a REST endpoint instead of an SMTP socket.
        """
        app = current_app._get_current_object()
        api_key = app.config['BREVO_API_KEY']
        sender = app.config['MAIL_DEFAULT_SENDER']

        # MAIL_DEFAULT_SENDER is stored as "Name <email@domain>" for
        # flask-mail compatibility; Brevo's API wants {name, email} separately.
        if '<' in sender and '>' in sender:
            sender_name = sender.split('<')[0].strip()
            sender_email = sender.split('<')[1].split('>')[0].strip()
        else:
            sender_name = app.config.get('APP_NAME', 'WorkPro')
            sender_email = sender

        payload = {
            'sender': {'name': sender_name, 'email': sender_email},
            'to': [{'email': recipient}],
            'subject': subject,
            'htmlContent': html,
        }
        headers = {
            'accept': 'application/json',
            'api-key': api_key,
            'content-type': 'application/json',
        }

        def _send():
            with app.app_context():
                try:
                    resp = requests.post(
                        'https://api.brevo.com/v3/smtp/email',
                        json=payload,
                        headers=headers,
                        timeout=10,
                    )
                    if resp.status_code >= 300:
                        current_app.logger.error(
                            f'Brevo send failed ({resp.status_code}): {resp.text}'
                        )
                except requests.RequestException as e:
                    # Network-level failure (DNS, connection, timeout). Logged
                    # only -- by this point the HTTP response to the original
                    # request has already been returned to the user.
                    current_app.logger.error(f'Async mail send failed: {e}')

        thread = threading.Thread(target=_send, daemon=True)
        thread.start()