from app import db
from app.models import Role, Permission, User
from app.models.subscription import Subscription


PERMISSIONS = [
    ('tasks.view',   'View tasks',    'tasks'),
    ('tasks.create', 'Create tasks',  'tasks'),
    ('tasks.edit',   'Edit tasks',    'tasks'),
    ('tasks.delete', 'Delete tasks',  'tasks'),
    ('planner.view',   'View planner',   'planner'),
    ('planner.create', 'Create plans',   'planner'),
    ('planner.edit',   'Edit plans',     'planner'),
    ('planner.delete', 'Delete plans',   'planner'),
    ('docs.view',   'View documents',   'docs'),
    ('docs.create', 'Create documents', 'docs'),
    ('docs.edit',   'Edit documents',   'docs'),
    ('docs.delete', 'Delete documents', 'docs'),
    ('users.view',   'View users',   'users'),
    ('users.create', 'Create users', 'users'),
    ('users.edit',   'Edit users',   'users'),
    ('users.delete', 'Delete users', 'users'),
    ('admin.access', 'Admin panel access', 'admin'),
    ('admin.roles',  'Manage roles',       'admin'),
]

ROLES = {
    'admin': {
        'description': 'Full system access',
        'permissions': [p[0] for p in PERMISSIONS],
        'is_default': False,
    },
    'manager': {
        'description': 'Team management access',
        'permissions': [
            'tasks.view','tasks.create','tasks.edit','tasks.delete',
            'planner.view','planner.create','planner.edit','planner.delete',
            'docs.view','docs.create','docs.edit','docs.delete',
            'users.view',
        ],
        'is_default': False,
    },
    'user': {
        'description': 'Standard user access',
        'permissions': [
            'tasks.view','tasks.create','tasks.edit','tasks.delete',
            'planner.view','planner.create','planner.edit','planner.delete',
            'docs.view','docs.create','docs.edit',
        ],
        'is_default': True,
    },
}


def seed_defaults():
    perm_map = {}
    for name, desc, module in PERMISSIONS:
        p = Permission.query.filter_by(name=name).first()
        if not p:
            p = Permission(name=name, description=desc, module=module)
            db.session.add(p)
            db.session.flush()
        perm_map[name] = p

    role_map = {}
    for role_name, cfg in ROLES.items():
        r = Role.query.filter_by(name=role_name).first()
        if not r:
            r = Role(name=role_name, description=cfg['description'], is_default=cfg['is_default'])
            db.session.add(r)
            db.session.flush()
        for pname in cfg['permissions']:
            if pname in perm_map and not r.has_permission(pname):
                r.add_permission(perm_map[pname])
        role_map[role_name] = r

    db.session.commit()

    admin_role = role_map['admin']
    if not User.query.filter_by(role_id=admin_role.id).first():
        admin = User(
            first_name  = 'Admin',
            last_name   = 'User',
            email       = 'admin@workpro.app',
            role_id     = admin_role.id,
            is_active   = True,
            is_verified = True,
            theme       = 'light',
        )
        admin.set_password('Admin@1234')
        db.session.add(admin)
        db.session.flush()

        # Give admin a Pro subscription by default
        sub = Subscription(user_id=admin.id, plan='pro', status='active')
        db.session.add(sub)
        db.session.commit()
        print('✅ Default admin created: admin@workpro.app / Admin@1234 (Pro plan)')
