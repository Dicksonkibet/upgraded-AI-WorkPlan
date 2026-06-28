from app import db, login_mgr
from flask_login import UserMixin
from datetime import datetime
import bcrypt
import secrets
from itsdangerous import URLSafeTimedSerializer
from flask import current_app


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80), nullable=False)
    last_name     = db.Column(db.String(80), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id       = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
    is_verified   = db.Column(db.Boolean, default=False)
    theme         = db.Column(db.String(10), default='light')
    avatar_color  = db.Column(db.String(10), default='#6c63ff')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login    = db.Column(db.DateTime)
    current_session_token = db.Column(db.String(64))
    phone                 = db.Column(db.String(20), nullable=True)   # M-Pesa payout number
    reset_token_nonce  = db.Column(db.String(16), nullable=True)
    verify_token_nonce = db.Column(db.String(16), nullable=True)

    # ── NEW: Onboarding & engagement ──────────────────────────────
    # onboarding_done: True once user completes the 3-step welcome flow
    onboarding_done       = db.Column(db.Boolean, default=False)
    # email_reminders: user opt-in for due-date email nudges
    email_reminders       = db.Column(db.Boolean, default=True)
    # streak_days: consecutive days with at least one task completed
    streak_days           = db.Column(db.Integer, default=0)
    streak_last_active    = db.Column(db.Date, nullable=True)

    role         = db.relationship('Role', backref='users', lazy='joined')
    tasks        = db.relationship('Task', backref='owner', lazy='dynamic', foreign_keys='Task.user_id')
    plans        = db.relationship('DailyPlan', backref='owner', lazy='dynamic')
    docs         = db.relationship('Document',  backref='owner', lazy='dynamic')
    logs         = db.relationship('ActivityLog', backref='user', lazy='dynamic')
    subscription = db.relationship('Subscription', backref='user', uselist=False)
    referral_code = db.relationship('ReferralCode', backref='owner', uselist=False)
    ai_usages    = db.relationship('AIUsage', backref='user', lazy='dynamic')

    # ── Password ──────────────────────────────────────────────────
    def set_password(self, raw):
        self.password_hash = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw):
        return bcrypt.checkpw(raw.encode(), self.password_hash.encode())

    # ── Tokens ────────────────────────────────────────────────────
    def get_reset_token(self):
        self.reset_token_nonce = secrets.token_hex(8)
        db.session.commit()
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(
            {'user_id': self.id, 'nonce': self.reset_token_nonce},
            salt='password-reset',
        )

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='password-reset', max_age=max_age)
        except Exception:
            return None
        user = User.query.get(data.get('user_id'))
        if not user or user.reset_token_nonce != data.get('nonce'):
            return None
        return user

    def get_verify_token(self):
        self.verify_token_nonce = secrets.token_hex(8)
        db.session.commit()
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(
            {'user_id': self.id, 'nonce': self.verify_token_nonce},
            salt='email-verify',
        )

    @staticmethod
    def verify_email_token(token, max_age=86400):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='email-verify', max_age=max_age)
        except Exception:
            return None
        user = User.query.get(data.get('user_id'))
        if not user or user.verify_token_nonce != data.get('nonce'):
            return None
        return user

    def invalidate_reset_token(self):
        """Rotate the reset nonce so a used/old reset link can never be replayed."""
        self.reset_token_nonce = None

    def invalidate_verify_token(self):
        """Rotate the verify nonce so a used/old verification link can never be replayed."""
        self.verify_token_nonce = None

    # ── Properties ────────────────────────────────────────────────
    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def initials(self):
        return f'{self.first_name[0]}{self.last_name[0]}'.upper()

    @property
    def is_pro(self):
        return bool(self.subscription and self.subscription.is_pro)

    @property
    def plan(self):
        if self.subscription and self.subscription.is_pro:
            return 'pro'
        return 'free'

    # ── Streak tracking ───────────────────────────────────────────
    def update_streak(self):
        """Call whenever the user completes a task. Updates streak_days."""
        from datetime import date, timedelta
        today = date.today()
        if self.streak_last_active == today:
            return  # already counted today
        if self.streak_last_active == today - timedelta(days=1):
            self.streak_days = (self.streak_days or 0) + 1
        else:
            self.streak_days = 1
        self.streak_last_active = today
        db.session.commit()

    # ── Roles ─────────────────────────────────────────────────────
    def is_admin(self):
        return self.role and self.role.name == 'admin'

    def is_manager(self):
        return bool(self.role and self.role.name == 'manager')

    def has_permission(self, perm_name):
        if not self.role:
            return False
        return any(p.name == perm_name for p in self.role.permissions)

    # ── Usage / limits ────────────────────────────────────────────
    def get_limits(self):
        from app.services.settings_service import settings_service
        if self.is_pro:
            return {'tasks': None, 'docs': None, 'ai_msgs': None}
        return {
            'tasks':   settings_service.get('free_tasks_limit'),
            'docs':    settings_service.get('free_docs_limit'),
            'ai_msgs': settings_service.get('free_ai_msg_limit'),
        }

    def get_usage(self):
        from datetime import date
        from app.models.subscription import AIUsage
        task_count = self.tasks.count()
        doc_count  = self.docs.count()
        usage = AIUsage.query.filter_by(user_id=self.id, date=date.today()).first()
        return {
            'tasks':   task_count,
            'docs':    doc_count,
            'ai_msgs': usage.msg_count if usage else 0,
        }

    def can_create_task(self):
        if self.is_pro:
            return True
        limits = self.get_limits()
        usage  = self.get_usage()
        return limits['tasks'] is None or usage['tasks'] < limits['tasks']

    def can_create_doc(self):
        if self.is_pro:
            return True
        limits = self.get_limits()
        usage  = self.get_usage()
        return limits['docs'] is None or usage['docs'] < limits['docs']

    def can_use_ai(self):
        if self.is_pro:
            return True
        limits = self.get_limits()
        usage  = self.get_usage()
        return usage['ai_msgs'] < limits['ai_msgs']

    def increment_ai_usage(self):
        from datetime import date
        from app.models.subscription import AIUsage
        today = date.today()
        row = AIUsage.query.filter_by(user_id=self.id, date=today).first()
        if not row:
            row = AIUsage(user_id=self.id, date=today, msg_count=0)
            db.session.add(row)
        row.msg_count += 1
        db.session.commit()

    def get_stats(self):
        from app.models import Task
        return {
            'total':       self.tasks.count(),
            'done':        self.tasks.filter_by(status='done').count(),
            'in_progress': self.tasks.filter_by(status='in_progress').count(),
            'todo':        self.tasks.filter_by(status='todo').count(),
        }

    def to_dict(self):
        return {
            'id':             self.id,
            'first_name':     self.first_name,
            'last_name':      self.last_name,
            'full_name':      self.full_name,
            'email':          self.email,
            'role':           self.role.name if self.role else None,
            'is_active':      self.is_active,
            'is_verified':    self.is_verified,
            'theme':          self.theme,
            'avatar_color':   self.avatar_color,
            'plan':           self.plan,
            'streak_days':    self.streak_days,
            'onboarding_done': self.onboarding_done,
            'created_at':     self.created_at.isoformat() if self.created_at else None,
            'last_login':     self.last_login.isoformat() if self.last_login else None,
            'phone':          self.phone,
        }


@login_mgr.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
