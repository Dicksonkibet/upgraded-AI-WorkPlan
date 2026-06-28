"""
Promotions / discount code service.
Admin creates codes; users apply them at checkout to reduce subscription price.
"""
from datetime import datetime
from app import db
from app.models.team import PromoCode, PromoUsage
from app.models.subscription import Payment


class PromoService:

    # ── Admin: create / manage ──────────────────────────────────────

    def create_code(self, admin_id: int, code: str, description: str,
                    discount_type: str, discount_value: float,
                    max_uses=None, valid_until=None) -> tuple:
        code = code.strip().upper()
        if not code or len(code) < 3:
            return None, 'Code must be at least 3 characters.'
        if len(code) > 30:
            return None, 'Code too long (max 30 chars).'
        if discount_type not in ('percent', 'fixed'):
            return None, 'Discount type must be percent or fixed.'
        if discount_value <= 0:
            return None, 'Discount value must be positive.'
        if discount_type == 'percent' and discount_value > 100:
            return None, 'Percentage discount cannot exceed 100%.'
        if PromoCode.query.filter_by(code=code).first():
            return None, f'Code "{code}" already exists.'

        promo = PromoCode(
            code=code,
            description=(description or '').strip()[:200],
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses if max_uses and max_uses > 0 else None,
            valid_until=valid_until,
            created_by=admin_id,
        )
        db.session.add(promo)
        db.session.commit()
        return promo, None

    def toggle_active(self, promo_id: int) -> tuple:
        p = PromoCode.query.get(promo_id)
        if not p:
            return False, 'Promo not found.'
        p.is_active = not p.is_active
        db.session.commit()
        return True, 'Active' if p.is_active else 'Inactive'

    def delete_code(self, promo_id: int) -> tuple:
        p = PromoCode.query.get(promo_id)
        if not p:
            return False, 'Promo not found.'
        db.session.delete(p)
        db.session.commit()
        return True, 'Deleted.'

    def list_all(self):
        return PromoCode.query.order_by(PromoCode.created_at.desc()).all()

    # ── User: validate & apply ──────────────────────────────────────

    def validate(self, code_str: str, user_id: int, amount: float) -> tuple:
        """
        Returns (promo, discount_kes, error).
        discount_kes is how much to deduct from `amount`.
        """
        promo = PromoCode.query.filter_by(code=code_str.strip().upper()).first()
        if not promo:
            return None, 0, 'Invalid promo code.'
        if not promo.is_valid:
            return None, 0, 'This promo code is expired or no longer active.'
        # Check if user already used it
        used = PromoUsage.query.filter_by(
            promo_code_id=promo.id, user_id=user_id
        ).first()
        if used:
            return None, 0, 'You have already used this promo code.'
        discount = promo.compute_discount(amount)
        return promo, discount, None

    def apply(self, promo: PromoCode, user_id: int,
              payment_id: int, discount_amt: float):
        """Record usage after a successful payment."""
        usage = PromoUsage(
            promo_code_id=promo.id,
            user_id=user_id,
            payment_id=payment_id,
            discount_amt=discount_amt,
        )
        db.session.add(usage)
        promo.used_count = (promo.used_count or 0) + 1
        db.session.commit()

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self, promo_id: int) -> dict:
        p = PromoCode.query.get(promo_id)
        if not p:
            return {}
        total_saved = db.session.query(
            db.func.sum(PromoUsage.discount_amt)
        ).filter_by(promo_code_id=promo_id).scalar() or 0
        return {
            'code':         p.code,
            'used_count':   p.used_count,
            'total_saved':  total_saved,
            'is_valid':     p.is_valid,
        }


promo_service = PromoService()
