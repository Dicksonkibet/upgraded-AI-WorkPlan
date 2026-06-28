from app import db
from datetime import datetime


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    plan           = db.Column(db.String(20), default='free')   # free | pro
    billing_cycle  = db.Column(db.String(20))                   # monthly | annual
    status         = db.Column(db.String(20), default='active') # active | cancelled | expired | pending
    amount_paid    = db.Column(db.Float, default=0)
    currency       = db.Column(db.String(10), default='KES')
    started_at     = db.Column(db.DateTime)
    expires_at     = db.Column(db.DateTime)
    cancelled_at   = db.Column(db.DateTime)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship('Payment', backref='subscription', lazy='dynamic')

    @property
    def is_pro(self):
        if self.plan != 'pro':
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return self.status == 'active'

    @property
    def is_active(self):
        return self.status == 'active'

    def to_dict(self):
        return {
            'plan':          self.plan,
            'billing_cycle': self.billing_cycle,
            'status':        self.status,
            'is_pro':        self.is_pro,
            'expires_at':    self.expires_at.isoformat() if self.expires_at else None,
            'started_at':    self.started_at.isoformat() if self.started_at else None,
        }


class Payment(db.Model):
    __tablename__ = 'payments'

    id                   = db.Column(db.Integer, primary_key=True)
    subscription_id      = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount               = db.Column(db.Float, nullable=False)
    currency             = db.Column(db.String(10), default='KES')
    status               = db.Column(db.String(20), default='pending')  # pending | completed | failed
    mpesa_checkout_id    = db.Column(db.String(100))
    mpesa_receipt        = db.Column(db.String(100))
    phone_number         = db.Column(db.String(20))
    billing_cycle        = db.Column(db.String(20))
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at         = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id':             self.id,
            'amount':         self.amount,
            'currency':       self.currency,
            'status':         self.status,
            'mpesa_receipt':  self.mpesa_receipt,
            'billing_cycle':  self.billing_cycle,
            'created_at':     self.created_at.isoformat(),
            'completed_at':   self.completed_at.isoformat() if self.completed_at else None,
        }


class AIUsage(db.Model):
    """Tracks daily AI message usage for free tier."""
    __tablename__ = 'ai_usage'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date       = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    msg_count  = db.Column(db.Integer, default=0)

    __table_args__ = (db.UniqueConstraint('user_id', 'date'),)
