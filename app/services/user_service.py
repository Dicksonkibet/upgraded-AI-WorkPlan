from app import db
from app.models import User, Role, ActivityLog
from app.interfaces import IUserService
from datetime import datetime


class UserService(IUserService):

    def get_all(self, page: int = 1, filters: dict = None):
        filters = filters or {}
        q = User.query
        if filters.get('role_id'):
            q = q.filter_by(role_id=filters['role_id'])
        if filters.get('is_active') is not None:
            q = q.filter_by(is_active=filters['is_active'])
        if filters.get('q'):
            term = f"%{filters['q']}%"
            q = q.filter(
                db.or_(User.first_name.ilike(term),
                       User.last_name.ilike(term),
                       User.email.ilike(term))
            )
        total = q.count()
        users = q.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
        return users, total

    def get_by_id(self, user_id: int):
        return User.query.get_or_404(user_id)

    def update(self, user_id: int, data: dict):
        user = User.query.get_or_404(user_id)
        try:
            for f in ('first_name', 'last_name', 'email', 'theme', 'avatar_color'):
                if f in data:
                    setattr(user, f, data[f])
            if data.get('password'):
                user.set_password(data['password'])
            user.updated_at = datetime.utcnow()
            db.session.commit()
            return user, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    def delete(self, user_id: int):
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return True

    def toggle_active(self, user_id: int):
        user = User.query.get_or_404(user_id)
        user.is_active = not user.is_active
        db.session.commit()
        return user.is_active

    def change_role(self, user_id: int, role_id: int):
        """Returns (success: bool, error_message: str|None)."""
        user = User.query.get_or_404(user_id)
        role = Role.query.get_or_404(role_id)

        if role.name == 'admin':
            existing_admin = User.query.join(Role).filter(
                Role.name == 'admin', User.id != user_id
            ).first()
            if existing_admin:
                return False, (
                    f'Only one admin account is allowed on this system. '
                    f'"{existing_admin.full_name}" is already the admin — '
                    f'change their role first if you want to replace them.'
                )

        user.role_id = role.id
        db.session.commit()
        return True, None

    def admin_exists(self, exclude_user_id: int = None):
        q = User.query.join(Role).filter(Role.name == 'admin')
        if exclude_user_id is not None:
            q = q.filter(User.id != exclude_user_id)
        return q.first() is not None

    def get_stats(self):
        return {
            'total':    User.query.count(),
            'active':   User.query.filter_by(is_active=True).count(),
            'inactive': User.query.filter_by(is_active=False).count(),
            'admins':   User.query.join(Role).filter(Role.name == 'admin').count(),
        }
