from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.services import task_service, plan_service, doc_service
from app.models import ActivityLog

api_bp = Blueprint('api', __name__)


def ok(data, code=200):
    return jsonify({'success': True, 'data': data}), code

def err(msg, code=400, upgrade=False):
    body = {'success': False, 'error': msg}
    if upgrade:
        body['upgrade'] = True
    return jsonify(body), code


# ── Tasks API ──────────────────────────────────────────────────────
@api_bp.route('/tasks', methods=['GET'])
@login_required
def api_tasks():
    tasks = task_service.get_all(current_user.id, request.args.to_dict())
    return ok([t.to_dict() for t in tasks])

@api_bp.route('/tasks', methods=['POST'])
@login_required
def api_create_task():
    if not current_user.can_create_task():
        return err(
            f'Free plan limit reached ({current_user.get_limits()["tasks"]} tasks). '
            f'Upgrade to Pro for unlimited tasks.',
            403, upgrade=True
        )
    task, e = task_service.create(current_user.id, request.json or {})
    return ok(task.to_dict(), 201) if task else err(e)

@api_bp.route('/tasks/<int:tid>', methods=['PUT'])
@login_required
def api_update_task(tid):
    task, e = task_service.update(tid, current_user.id, request.json or {})
    return ok(task.to_dict()) if task else err(e)

@api_bp.route('/tasks/<int:tid>', methods=['DELETE'])
@login_required
def api_delete_task(tid):
    return ok({'deleted': task_service.delete(tid, current_user.id)})


# ── Plans API ──────────────────────────────────────────────────────
@api_bp.route('/plans', methods=['GET'])
@login_required
def api_plans():
    d = request.args.get('date', '')
    return ok([p.to_dict() for p in plan_service.get_by_date(current_user.id, d)])

@api_bp.route('/plans', methods=['POST'])
@login_required
def api_create_plan():
    plan, e = plan_service.create(current_user.id, request.json or {})
    return ok(plan.to_dict(), 201) if plan else err(e)

@api_bp.route('/plans/<int:pid>', methods=['PUT'])
@login_required
def api_update_plan(pid):
    plan, e = plan_service.update(pid, current_user.id, request.json or {})
    return ok(plan.to_dict()) if plan else err(e)

@api_bp.route('/plans/<int:pid>', methods=['DELETE'])
@login_required
def api_delete_plan(pid):
    return ok({'deleted': plan_service.delete(pid, current_user.id)})


# ── Docs API ───────────────────────────────────────────────────────
@api_bp.route('/documents', methods=['GET'])
@login_required
def api_docs():
    return ok([d.to_dict() for d in doc_service.get_all(current_user.id, request.args.to_dict())])

@api_bp.route('/documents', methods=['POST'])
@login_required
def api_create_doc():
    if not current_user.can_create_doc():
        return err(
            f'Free plan limit reached ({current_user.get_limits()["docs"]} docs). '
            f'Upgrade to Pro for unlimited documents.',
            403, upgrade=True
        )
    doc, e = doc_service.create(current_user.id, request.json or {})
    return ok(doc.to_dict(), 201) if doc else err(e)

@api_bp.route('/documents/<int:did>', methods=['PUT'])
@login_required
def api_update_doc(did):
    doc, e = doc_service.update(did, current_user.id, request.json or {})
    return ok(doc.to_dict()) if doc else err(e)

@api_bp.route('/documents/<int:did>', methods=['DELETE'])
@login_required
def api_delete_doc(did):
    return ok({'deleted': doc_service.delete(did, current_user.id)})


# ── Logs API ───────────────────────────────────────────────────────
@api_bp.route('/logs', methods=['GET'])
@login_required
def api_logs():
    logs = ActivityLog.query.filter_by(user_id=current_user.id)\
        .order_by(ActivityLog.created_at.desc()).limit(50).all()
    return ok([l.to_dict() for l in logs])


# ── User context API ───────────────────────────────────────────────
@api_bp.route('/me', methods=['GET'])
@login_required
def api_me():
    return ok({
        **current_user.to_dict(),
        'limits': current_user.get_limits(),
        'usage':  current_user.get_usage(),
        'is_pro': current_user.is_pro,
    })


# ── Subscription status ────────────────────────────────────────────
@api_bp.route('/subscription', methods=['GET'])
@login_required
def api_subscription():
    from app.models.subscription import Subscription
    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    return ok(sub.to_dict() if sub else {'plan': 'free', 'is_pro': False})
