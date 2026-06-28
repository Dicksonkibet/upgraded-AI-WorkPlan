"""
Referral & Commission system.

Flow:
  1. User A shares their referral link (contains ref=<code>)
  2. User B registers via that link — ReferralSignup is created
  3. User B pays for Pro — Commission is created (% of payment)
  4. Commission auto-pays to User A's M-Pesa via B2C (or marks as pending)
"""

from app import db
from datetime import datetime
import secrets


class ReferralCode(db.Model):
    __tablename__ = 'referral_codes'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    code       = db.Column(db.String(12), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    signups     = db.relationship('ReferralSignup', backref='referral_code', lazy='dynamic')
    commissions = db.relationship('Commission',     backref='referral_code', lazy='dynamic')

    @staticmethod
    def generate_code():
        return secrets.token_urlsafe(8)[:8].upper()

    @property
    def total_signups(self):
        return self.signups.count()

    @property
    def converted_signups(self):
        return self.signups.filter_by(converted=True).count()

    @property
    def total_earned(self):
        total = db.session.query(
            db.func.sum(Commission.amount)
        ).filter_by(referral_code_id=self.id, status='paid').scalar()
        return total or 0.0

    @property
    def pending_earnings(self):
        total = db.session.query(
            db.func.sum(Commission.amount)
        ).filter_by(referral_code_id=self.id, status='pending').scalar()
        return total or 0.0


class ReferralSignup(db.Model):
    """Records when someone registers using a referral code."""
    __tablename__ = 'referral_signups'

    id               = db.Column(db.Integer, primary_key=True)
    referral_code_id = db.Column(db.Integer, db.ForeignKey('referral_codes.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    converted        = db.Column(db.Boolean, default=False)   # True once they pay
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    converted_at     = db.Column(db.DateTime, nullable=True)

    referred_user = db.relationship('User', foreign_keys=[referred_user_id])


class Commission(db.Model):
    """Commission earned by the referrer when referred user pays."""
    __tablename__ = 'commissions'

    id               = db.Column(db.Integer, primary_key=True)
    referral_code_id = db.Column(db.Integer, db.ForeignKey('referral_codes.id'), nullable=False)
    referrer_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payment_id       = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    amount           = db.Column(db.Float, nullable=False)        # KES amount
    rate             = db.Column(db.Float, nullable=False)        # commission % used
    status           = db.Column(db.String(20), default='pending')  # pending | paid | failed
    mpesa_receipt    = db.Column(db.String(100), nullable=True)
    phone_number     = db.Column(db.String(20), nullable=True)   # referrer's payout phone
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at          = db.Column(db.DateTime, nullable=True)
    notes            = db.Column(db.String(255), nullable=True)

    referrer      = db.relationship('User', foreign_keys=[referrer_id])
    referred_user = db.relationship('User', foreign_keys=[referred_user_id])
    payment       = db.relationship('Payment', foreign_keys=[payment_id])

    def to_dict(self):
        return {
            'id':            self.id,
            'amount':        self.amount,
            'rate':          self.rate,
            'status':        self.status,
            'mpesa_receipt': self.mpesa_receipt,
            'created_at':    self.created_at.isoformat(),
            'paid_at':       self.paid_at.isoformat() if self.paid_at else None,
            'referred_user': self.referred_user.full_name if self.referred_user else None,
        }
