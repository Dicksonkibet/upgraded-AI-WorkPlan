"""
Team & Promotions models.

Teams:
  - A team has one owner (creator) and many members
  - Members have roles: owner, admin, member
  - Teams enable shared task visibility and leaderboards

Promotions / Discount Codes:
  - Admin creates promo codes with a percentage or fixed KES discount
  - Applied at checkout; validated once per user
  - Tracks usage count and expiry
"""

from app import db
from datetime import datetime
import secrets
import string


class Team(db.Model):
    __tablename__ = 'teams'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    slug        = db.Column(db.String(60), unique=True, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    owner_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner   = db.relationship('User', foreign_keys=[owner_id], backref='owned_teams')
    members = db.relationship('TeamMember', backref='team', lazy='dynamic',
                              cascade='all, delete-orphan')

    @staticmethod
    def generate_invite_code():
        chars = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = ''.join(secrets.choice(chars) for _ in range(8))
            if not Team.query.filter_by(invite_code=code).first():
                return code
        return secrets.token_urlsafe(6).upper()[:8]

    @staticmethod
    def slugify(name: str) -> str:
        import re
        s = name.lower().strip()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'[\s-]+', '-', s)
        s = s.strip('-')
        base = s[:50] or 'team'
        slug = base
        n = 1
        while Team.query.filter_by(slug=slug).first():
            slug = f'{base}-{n}'
            n += 1
        return slug

    @property
    def member_count(self):
        return self.members.filter_by(is_active=True).count()

    @property
    def active_members(self):
        return self.members.filter_by(is_active=True).all()

    def is_owner(self, user_id: int) -> bool:
        return self.owner_id == user_id

    def is_admin_or_owner(self, user_id: int) -> bool:
        if self.owner_id == user_id:
            return True
        m = self.members.filter_by(user_id=user_id, is_active=True).first()
        return bool(m and m.role in ('owner', 'admin'))

    def get_member(self, user_id: int):
        return self.members.filter_by(user_id=user_id, is_active=True).first()

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'slug':        self.slug,
            'description': self.description,
            'invite_code': self.invite_code,
            'member_count': self.member_count,
            'created_at':  self.created_at.isoformat(),
        }


class TeamMember(db.Model):
    __tablename__ = 'team_members'

    id         = db.Column(db.Integer, primary_key=True)
    team_id    = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role       = db.Column(db.String(20), default='member')  # owner | admin | member
    is_active  = db.Column(db.Boolean, default=True)
    joined_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='team_memberships')

    __table_args__ = (db.UniqueConstraint('team_id', 'user_id'),)

    def to_dict(self):
        return {
            'id':        self.id,
            'user_id':   self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'user_email': self.user.email if self.user else None,
            'role':      self.role,
            'joined_at': self.joined_at.isoformat(),
        }


# ── Promotions ─────────────────────────────────────────────────────────────────

class PromoCode(db.Model):
    """Discount codes created by admin, applied at checkout."""
    __tablename__ = 'promo_codes'

    id            = db.Column(db.Integer, primary_key=True)
    code          = db.Column(db.String(30), unique=True, nullable=False, index=True)
    description   = db.Column(db.String(200), nullable=True)
    discount_type = db.Column(db.String(10), nullable=False)   # percent | fixed
    discount_value = db.Column(db.Float, nullable=False)       # % or KES amount
    max_uses      = db.Column(db.Integer, nullable=True)       # None = unlimited
    used_count    = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    valid_from    = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until   = db.Column(db.DateTime, nullable=True)      # None = no expiry
    created_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    creator   = db.relationship('User', foreign_keys=[created_by])
    usages    = db.relationship('PromoUsage', backref='promo_code', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def is_valid(self):
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def compute_discount(self, original_amount: float) -> float:
        """Return the KES amount to deduct."""
        if self.discount_type == 'percent':
            return round(original_amount * self.discount_value / 100, 2)
        else:  # fixed
            return min(self.discount_value, original_amount)

    def to_dict(self):
        return {
            'id':             self.id,
            'code':           self.code,
            'description':    self.description,
            'discount_type':  self.discount_type,
            'discount_value': self.discount_value,
            'max_uses':       self.max_uses,
            'used_count':     self.used_count,
            'is_active':      self.is_active,
            'is_valid':       self.is_valid,
            'valid_until':    self.valid_until.isoformat() if self.valid_until else None,
            'created_at':     self.created_at.isoformat(),
        }


class PromoUsage(db.Model):
    """Records one promo usage per (user, promo) pair."""
    __tablename__ = 'promo_usages'

    id            = db.Column(db.Integer, primary_key=True)
    promo_code_id = db.Column(db.Integer, db.ForeignKey('promo_codes.id'), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payment_id    = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    discount_amt  = db.Column(db.Float, nullable=False)   # actual KES saved
    used_at       = db.Column(db.DateTime, default=datetime.utcnow)

    user    = db.relationship('User', foreign_keys=[user_id])
    payment = db.relationship('Payment', foreign_keys=[payment_id])

    __table_args__ = (db.UniqueConstraint('promo_code_id', 'user_id'),)
