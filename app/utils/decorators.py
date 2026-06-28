from functools import wraps
from flask import abort, flash, redirect, url_for, jsonify, request
from flask_login import current_user


def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            # Admin bypasses ALL permission checks
            if current_user.is_admin():
                return f(*args, **kwargs)
            if not current_user.has_permission(perm):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_manager():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def pro_required(f):
    """Blocks free users from Pro-only features."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # Admin always has pro access
        if current_user.is_admin():
            return f(*args, **kwargs)
        if not current_user.is_pro:
            if request.is_json:
                return jsonify({'error': 'Pro plan required', 'upgrade': True}), 403
            flash('This feature requires a Pro plan. Upgrade to unlock.', 'warning')
            return redirect(url_for('subscription.index'))
        return f(*args, **kwargs)
    return decorated


# Sidebar menu
SIDEBAR_MENUS = [
    {
        'section': 'Main',
        'items': [
            {'label': 'Dashboard',     'icon': 'bi-speedometer2',  'endpoint': 'dashboard.index',   'perm': None,          'admin_only': False},
            {'label': 'My Tasks',      'icon': 'bi-check2-square', 'endpoint': 'tasks.index',       'perm': 'tasks.view',  'admin_only': False},
            {'label': 'Daily Planner', 'icon': 'bi-calendar3',     'endpoint': 'planner.index',     'perm': 'planner.view','admin_only': False},
        ]
    },
    {
        'section': 'Work',
        'items': [
            {'label': 'Documentation', 'icon': 'bi-file-text',     'endpoint': 'docs.index',        'perm': 'docs.view',   'admin_only': False},
            {'label': 'Activity Log',  'icon': 'bi-clock-history', 'endpoint': 'dashboard.logs',    'perm': None,          'admin_only': False},
            {'label': 'AI Assistant',  'icon': 'bi-robot',         'endpoint': 'ai.chat',           'perm': None,          'admin_only': False},
        ]
    },
    {
        'section': 'Account',
        'items': [
            {'label': 'Subscription',  'icon': 'bi-stars',         'endpoint': 'subscription.index','perm': None,          'admin_only': False},
            {'label': 'Teams',         'icon': 'bi-people-fill',   'endpoint': 'teams.index',       'perm': None,          'admin_only': False},
            {'label': 'Referral',      'icon': 'bi-gift',          'endpoint': 'referral.index',    'perm': None,          'admin_only': False},
            {'label': 'Help & Support','icon': 'bi-question-circle','endpoint': 'help.index',       'perm': None,          'admin_only': False},
            {'label': 'Users',         'icon': 'bi-people',        'endpoint': 'users.index',       'perm': 'users.view',  'admin_only': False},
            {'label': 'Admin Panel',   'icon': 'bi-shield-check',  'endpoint': 'admin.index',       'perm': 'admin.access','admin_only': True},
        ]
    },
]


def get_visible_menus(user):
    is_admin = user.is_authenticated and user.is_admin()
    result = []
    for section in SIDEBAR_MENUS:
        items = []
        for item in section['items']:
            # Admin sees everything
            if is_admin:
                items.append(item)
                continue
            # Admin-only items hidden from non-admins
            if item.get('admin_only'):
                continue
            # Show if no permission needed or user has it
            if item['perm'] is None or user.has_permission(item['perm']):
                items.append(item)
        if items:
            result.append({'section': section['section'], 'items': items})
    return result