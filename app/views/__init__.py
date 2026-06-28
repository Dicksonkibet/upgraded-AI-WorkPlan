from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from app.utils.decorators import permission_required, admin_required, get_visible_menus
from app.services import task_service, plan_service, doc_service, user_service, ai_service, settings_service
from app.models import ActivityLog, Role, User, Task, DailyPlan, Document
from app import db
from datetime import date, datetime

# ── Dashboard ─────────────────────────────────────────────────────
dash_bp = Blueprint('dashboard', __name__)

@dash_bp.route('/')
@login_required
def index():
    stats = {
        'total_tasks': Task.query.filter(Task.user_id == current_user.id).count(),
        'in_progress': Task.query.filter_by(user_id=current_user.id, status='in_progress').count(),
        'done':        Task.query.filter_by(user_id=current_user.id, status='done').count(),
        'todo':        Task.query.filter_by(user_id=current_user.id, status='todo').count(),
        'today_plans': DailyPlan.query.filter_by(user_id=current_user.id, plan_date=date.today()).count(),
        'total_docs':  Document.query.filter_by(user_id=current_user.id).count(),
    }
    high_tasks  = Task.query.filter_by(user_id=current_user.id, priority='high', status='todo').limit(5).all()
    recent_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.created_at.desc()).limit(10).all()
    usage  = current_user.get_usage()
    limits = current_user.get_limits()
    return render_template('dashboard/index.html',
        stats=stats, high_tasks=high_tasks, recent_logs=recent_logs,
        usage=usage, limits=limits,
        menus=get_visible_menus(current_user))

@dash_bp.route('/logs')
@login_required
def logs():
    logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.created_at.desc()).limit(100).all()
    return render_template('dashboard/logs.html', logs=logs, menus=get_visible_menus(current_user))

@dash_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    error = None
    if request.method == 'POST':
        data = {k: v for k, v in request.form.items() if v}
        _, err = user_service.update(current_user.id, data)
        if err:
            error = err
        else:
            flash('Profile updated.', 'success')
    return render_template('dashboard/profile.html', error=error, menus=get_visible_menus(current_user))

@dash_bp.route('/update-phone', methods=['POST'])
@login_required
def update_phone():
    phone = request.form.get('phone', '').strip()
    if phone:
        current_user.phone = phone
        db.session.commit()
        flash('Payout phone updated.', 'success')
    return redirect(url_for('referral.index'))

@dash_bp.route('/toggle-theme', methods=['POST'])
@login_required
def toggle_theme():
    new_theme = 'light' if current_user.theme == 'dark' else 'dark'
    current_user.theme = new_theme
    db.session.commit()
    return jsonify({'theme': new_theme})




# ── Onboarding ────────────────────────────────────────────────────
@dash_bp.route('/onboarding/dismiss', methods=['POST'])
@login_required
def dismiss_onboarding():
    current_user.onboarding_done = True
    db.session.commit()
    return jsonify({'ok': True})


# ── Tasks ─────────────────────────────────────────────────────────
tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/')
@login_required
@permission_required('tasks.view')
def index():
    filters = {k: v for k, v in request.args.items() if v}
    tasks   = task_service.get_all(current_user.id, filters)
    users   = User.query.filter_by(is_active=True).all()
    usage   = current_user.get_usage()
    limits  = current_user.get_limits()
    return render_template('tasks/index.html', tasks=tasks, users=users,
        filters=filters, usage=usage, limits=limits,
        menus=get_visible_menus(current_user))

@tasks_bp.route('/create', methods=['POST'])
@login_required
@permission_required('tasks.create')
def create():
    if not current_user.can_create_task():
        flash(f'Task limit reached for Free plan. Upgrade to Pro for unlimited tasks.', 'warning')
        return redirect(url_for('subscription.index'))
    task, err = task_service.create(current_user.id, request.form.to_dict())
    if err:
        flash(f'Error: {err}', 'danger')
    else:
        flash('Task created.', 'success')
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/<int:task_id>/edit', methods=['POST'])
@login_required
@permission_required('tasks.edit')
def edit(task_id):
    _, err = task_service.update(task_id, current_user.id, request.form.to_dict())
    flash(f'Error: {err}' if err else 'Task updated.', 'danger' if err else 'success')
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
@permission_required('tasks.delete')
def delete(task_id):
    task_service.delete(task_id, current_user.id)
    flash('Task deleted.', 'success')
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/<int:task_id>/status', methods=['POST'])
@login_required
@permission_required('tasks.edit')
def update_status(task_id):
    data = request.get_json()
    new_status = data.get('status')
    task, _ = task_service.update(task_id, current_user.id, {'status': new_status})
    if new_status == 'done':
        current_user.update_streak()
    return jsonify(task.to_dict() if task else {'error': 'not found'})


# ── Planner ───────────────────────────────────────────────────────
planner_bp = Blueprint('planner', __name__)

@planner_bp.route('/')
@login_required
@permission_required('planner.view')
def index():
    d     = request.args.get('date', date.today().isoformat())
    plans = plan_service.get_by_date(current_user.id, d)
    return render_template('planner/index.html', plans=plans, plan_date=d,
        menus=get_visible_menus(current_user))

@planner_bp.route('/create', methods=['POST'])
@login_required
@permission_required('planner.create')
def create():
    _, err = plan_service.create(current_user.id, request.form.to_dict())
    flash(f'Error: {err}' if err else 'Plan added.', 'danger' if err else 'success')
    return redirect(url_for('planner.index'))

@planner_bp.route('/<int:plan_id>/toggle', methods=['POST'])
@login_required
@permission_required('planner.edit')
def toggle(plan_id):
    data = request.get_json()
    plan, _ = plan_service.update(plan_id, current_user.id, {'completed': data.get('completed')})
    return jsonify(plan.to_dict() if plan else {'error': 'not found'})

@planner_bp.route('/<int:plan_id>/delete', methods=['POST'])
@login_required
@permission_required('planner.delete')
def delete(plan_id):
    plan_service.delete(plan_id, current_user.id)
    flash('Plan removed.', 'success')
    return redirect(url_for('planner.index'))


# ── Docs ──────────────────────────────────────────────────────────
docs_bp = Blueprint('docs', __name__)

@docs_bp.route('/')
@login_required
@permission_required('docs.view')
def index():
    filters = {k: v for k, v in request.args.items() if v}
    docs    = doc_service.get_all(current_user.id, filters)
    usage   = current_user.get_usage()
    limits  = current_user.get_limits()
    return render_template('docs/index.html', docs=docs, filters=filters,
        usage=usage, limits=limits, menus=get_visible_menus(current_user))

@docs_bp.route('/<int:doc_id>')
@login_required
@permission_required('docs.view')
def view(doc_id):
    doc = doc_service.get_by_id(doc_id, current_user.id)
    if not doc:
        flash('Document not found.', 'danger')
        return redirect(url_for('docs.index'))
    return render_template('docs/view.html', doc=doc, menus=get_visible_menus(current_user))

@docs_bp.route('/create', methods=['POST'])
@login_required
@permission_required('docs.create')
def create():
    if not current_user.can_create_doc():
        flash('Document limit reached. Upgrade to Pro for unlimited documents.', 'warning')
        return redirect(url_for('subscription.index'))
    data = request.form.to_dict()
    data['is_shared'] = 'is_shared' in request.form
    _, err = doc_service.create(current_user.id, data)
    flash(f'Error: {err}' if err else 'Document saved.', 'danger' if err else 'success')
    return redirect(url_for('docs.index'))

@docs_bp.route('/<int:doc_id>/edit', methods=['POST'])
@login_required
@permission_required('docs.edit')
def edit(doc_id):
    data = request.form.to_dict()
    data['is_shared'] = 'is_shared' in request.form
    _, err = doc_service.update(doc_id, current_user.id, data)
    flash(f'Error: {err}' if err else 'Document updated.', 'danger' if err else 'success')
    return redirect(url_for('docs.view', doc_id=doc_id))

@docs_bp.route('/<int:doc_id>/delete', methods=['POST'])
@login_required
@permission_required('docs.delete')
def delete(doc_id):
    doc_service.delete(doc_id, current_user.id)
    flash('Document deleted.', 'success')
    return redirect(url_for('docs.index'))


# ── Admin ─────────────────────────────────────────────────────────
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
@admin_required
def index():
    from app.models.subscription import Subscription, AIUsage
    from datetime import date as today_date
    total_ai = db.session.query(db.func.sum(AIUsage.msg_count)).scalar() or 0
    stats = {
        'users':         user_service.get_stats(),
        'tasks':         {'total': Task.query.count(), 'done': Task.query.filter_by(status='done').count()},
        'docs':          Document.query.count(),
        'logs':          ActivityLog.query.count(),
        'pro_users':     Subscription.query.filter_by(plan='pro', status='active').count(),
        'ai_total_msgs': total_ai,
    }
    roles    = Role.query.all()
    all_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    return render_template('admin/index.html', stats=stats, roles=roles,
        logs=all_logs, settings=settings_service.get_all(),
        menus=get_visible_menus(current_user))

@admin_bp.route('/settings', methods=['POST'])
@login_required
@admin_required
def update_settings():
    errors = settings_service.update(request.form.to_dict())
    if errors:
        for msg in errors.values():
            flash(msg, 'danger')
    else:
        flash('Settings updated.', 'success')
    return redirect(url_for('admin.index') + '#settings')

@admin_bp.route('/roles/create', methods=['POST'])
@login_required
@admin_required
def create_role():
    name = request.form.get('name', '').strip()
    if name and not Role.query.filter_by(name=name).first():
        r = Role(name=name, description=request.form.get('description', ''))
        db.session.add(r)
        db.session.commit()
        flash(f'Role "{name}" created.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/roles/<int:role_id>/permissions', methods=['POST'])
@login_required
@admin_required
def update_permissions(role_id):
    from app.models import Permission
    role  = Role.query.get_or_404(role_id)
    perms = request.form.getlist('permissions')
    for p in role.permissions.all():
        role.permissions.remove(p)
    for pname in perms:
        p = Permission.query.filter_by(name=pname).first()
        if p:
            role.permissions.append(p)
    db.session.commit()
    flash('Permissions updated.', 'success')
    return redirect(url_for('admin.index'))


# ── Promo Code Admin ──────────────────────────────────────────────

@admin_bp.route('/promos')
@login_required
@admin_required
def promos():
    from app.services.promo_service import promo_service
    codes = promo_service.list_all()
    return render_template('admin/promos.html',
        codes=codes,
        menus=get_visible_menus(current_user))

@admin_bp.route('/promos/create', methods=['POST'])
@login_required
@admin_required
def create_promo():
    from app.services.promo_service import promo_service
    from datetime import datetime
    valid_until = None
    vu = request.form.get('valid_until', '').strip()
    if vu:
        try:
            valid_until = datetime.strptime(vu, '%Y-%m-%d')
        except ValueError:
            flash('Invalid expiry date format.', 'danger')
            return redirect(url_for('admin.promos'))

    max_uses = request.form.get('max_uses', '').strip()
    max_uses = int(max_uses) if max_uses.isdigit() else None

    _, err = promo_service.create_code(
        admin_id=current_user.id,
        code=request.form.get('code', '').strip(),
        description=request.form.get('description', '').strip(),
        discount_type=request.form.get('discount_type', 'percent'),
        discount_value=float(request.form.get('discount_value', 0) or 0),
        max_uses=max_uses,
        valid_until=valid_until,
    )
    flash(err or 'Promo code created.', 'danger' if err else 'success')
    return redirect(url_for('admin.promos'))

@admin_bp.route('/promos/<int:promo_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_promo(promo_id):
    from app.services.promo_service import promo_service
    _, msg = promo_service.toggle_active(promo_id)
    flash(msg, 'info')
    return redirect(url_for('admin.promos'))

@admin_bp.route('/promos/<int:promo_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_promo(promo_id):
    from app.services.promo_service import promo_service
    ok, msg = promo_service.delete_code(promo_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('admin.promos'))


# ── Users ─────────────────────────────────────────────────────────
users_bp = Blueprint('users', __name__)

@users_bp.route('/')
@login_required
@permission_required('users.view')
def index():
    page    = int(request.args.get('page', 1))
    filters = {k: v for k, v in request.args.items() if v and k != 'page'}
    users, total = user_service.get_all(page, filters)
    roles   = Role.query.all()
    return render_template('users/index.html', users=users, total=total,
        roles=roles, filters=filters, admin_exists=user_service.admin_exists(),
        menus=get_visible_menus(current_user))

@users_bp.route('/<int:user_id>/toggle', methods=['POST'])
@login_required
@permission_required('users.edit')
def toggle_active(user_id):
    state = user_service.toggle_active(user_id)
    flash(f'User {"activated" if state else "deactivated"}.', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/<int:user_id>/role', methods=['POST'])
@login_required
@permission_required('users.edit')
def change_role(user_id):
    ok, err = user_service.change_role(user_id, int(request.form.get('role_id')))
    flash(err if err else 'Role updated.', 'danger' if err else 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@permission_required('users.delete')
def delete(user_id):
    if user_id == current_user.id:
        flash("You can't delete yourself.", 'danger')
    else:
        user_service.delete(user_id)
        flash('User deleted.', 'success')
    return redirect(url_for('users.index'))


# ── AI ────────────────────────────────────────────────────────────
ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/')
@login_required
def chat():
    usage   = current_user.get_usage()
    limits  = current_user.get_limits()
    trial_remaining = ai_service.trial_tasks_remaining(current_user)
    return render_template('ai/chat.html',
        usage=usage, limits=limits,
        trial_tasks_remaining=trial_remaining,
        menus=get_visible_menus(current_user))

@ai_bp.route('/message', methods=['POST'])
@login_required
def message():
    # Check AI usage limit for free users
    if not current_user.can_use_ai():
        limits = current_user.get_limits()
        return jsonify({
            'reply': f"You've reached your daily AI message limit ({limits['ai_msgs']} messages/day) on the Free plan. "
                     f"Upgrade to Pro for unlimited AI access.",
            'limit_reached': True,
            'upgrade': True
        })

    data     = request.get_json()
    messages = data.get('messages', [])
    service  = data.get('service')
    reply    = ai_service.chat(current_user, messages, service=service)

    # Parse and optionally execute action
    action_data, clean_reply = ai_service.parse_action(reply)
    action_result = None

    trial_remaining = ai_service.trial_tasks_remaining(current_user)
    can_act = current_user.is_pro or trial_remaining > 0

    if action_data and can_act:
        needs_confirm = action_data.get('action', '').startswith('delete_')
        if needs_confirm and not data.get('confirmed'):
            return jsonify({
                'reply': clean_reply,
                'pending_action': action_data,
                'confirm_required': True,
                'confirm_msg': f'Are you sure you want to {action_data["action"].replace("_", " ")}?',
            })
        action_result = ai_service.execute_action(current_user, action_data)

    # Track usage
    current_user.increment_ai_usage()

    return jsonify({
        'reply':         clean_reply,
        'action_result': action_result,
    })

@ai_bp.route('/execute-action', methods=['POST'])
@login_required
def execute_action():
    """Execute a confirmed AI action."""
    if not current_user.is_pro:
        return jsonify({'error': 'Pro plan required'}), 403
    data        = request.get_json()
    action_data = data.get('action_data')
    if not action_data:
        return jsonify({'error': 'No action data'}), 400
    result = ai_service.execute_action(current_user, action_data)
    return jsonify(result)

@ai_bp.route('/report', methods=['POST'])
@login_required
def generate_report_route():
    if not current_user.can_use_ai():
        limits = current_user.get_limits()
        return jsonify({
            'error': f"Daily AI limit reached ({limits['ai_msgs']}/day). Upgrade to Pro.",
            'upgrade': True
        }), 429
    data        = request.get_json() or {}
    report_type = data.get('report_type', 'productivity')
    result      = ai_service.generate_report(current_user, report_type)
    current_user.increment_ai_usage()
    return jsonify(result)

@ai_bp.route('/summarize-tasks', methods=['POST'])
@login_required
def summarize_tasks():
    if not current_user.can_use_ai():
        return jsonify({'reply': 'Daily AI limit reached. Upgrade to Pro.', 'upgrade': True})
    summary = ai_service.summarize_tasks(current_user)
    current_user.increment_ai_usage()
    return jsonify({'reply': summary})

@ai_bp.route('/suggest-plan', methods=['POST'])
@login_required
def suggest_plan():
    if not current_user.can_use_ai():
        return jsonify({'reply': 'Daily AI limit reached. Upgrade to Pro.', 'upgrade': True})
    d = request.get_json().get('date', date.today().isoformat())
    plan = ai_service.suggest_plan(current_user, d)
    current_user.increment_ai_usage()
    return jsonify({'reply': plan})

@ai_bp.route('/generate-doc', methods=['POST'])
@login_required
def generate_doc():
    if not current_user.is_pro:
        return jsonify({'reply': 'AI document generation requires a Pro plan.', 'upgrade': True})
    data    = request.get_json()
    content = ai_service.generate_doc(current_user, data.get('type', 'report'), data.get('context', ''))
    return jsonify({'reply': content})
