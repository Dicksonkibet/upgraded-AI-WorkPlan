from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    from app.models import User, Task, Document
    from app.models.subscription import Subscription
    from app.services.settings_service import settings_service

    # ── Live stats from DB ────────────────────────────────────────────
    stats = {
        'users': User.query.filter_by(is_active=True).count(),
        'tasks': Task.query.count(),
        'docs':  Document.query.count(),
        'pro':   Subscription.query.filter_by(plan='pro', status='active').count(),
    }

    # ── Pricing from admin settings ───────────────────────────────────
    pricing = {
        'monthly': settings_service.get('pro_monthly_price'),
        'annual':  settings_service.get('pro_annual_price'),
    }

    # ── AI config for landing page display ───────────────────────────
    ai_config = {
        'persona_name': settings_service.get('ai_persona_name') or 'WorkPro AI Agent',
        'tone':         settings_service.get('ai_response_tone') or 'professional',
        'trial_limit':  settings_service.get('ai_trial_task_limit') or 20,
        'model':        settings_service.get('ai_model') or 'llama-3.1-8b-instant',
    }

    return render_template(
        'landing.html',
        stats=stats,
        pricing=pricing,
        ai_config=ai_config,
    )