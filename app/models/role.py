from app import db
from datetime import datetime

# Association table: roles <-> permissions
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)


class Permission(db.Model):
    __tablename__ = 'permissions'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)   # e.g. 'tasks.create'
    description = db.Column(db.String(255))
    module      = db.Column(db.String(50))   # tasks / planner / docs / admin / users

    def __repr__(self):
        return f'<Permission {self.name}>'


class Role(db.Model):
    __tablename__ = 'roles'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), unique=True, nullable=False)   # admin / manager / user
    description = db.Column(db.String(255))
    is_default  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles', lazy='dynamic')

    def has_permission(self, perm_name):
        return self.permissions.filter_by(name=perm_name).first() is not None

    def add_permission(self, perm):
        if not self.has_permission(perm.name):
            self.permissions.append(perm)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': [p.name for p in self.permissions],
        }

    def __repr__(self):
        return f'<Role {self.name}>'
