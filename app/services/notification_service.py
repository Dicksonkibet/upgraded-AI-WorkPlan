"""
notification_service.py
────────────────────────
Handles:
  • Due-date email reminders (tasks due today or tomorrow)
  • Daily digest email ("Here's your plan for today")
  • Recurring task spawning (daily/weekly/monthly)

Run the cron via Flask CLI:
    flask notify send-reminders
    flask notify daily-digest
    flask notify spawn-recurring

Or call directly in a scheduler (APScheduler, Celery beat, cron job).
"""

import click
from datetime import date, timedelta
from flask import current_app, render_template_string
from flask.cli import with_appcontext

# ── Email helper ──────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body_html: str):
    """
    Send transactional email via Brevo's HTTP API — the same approach used
    by auth_service.py for verification/reset emails. Flask-Mail is never
    initialized anywhere in this app (no Mail() instance, no init_app), so
    routing through it here would silently no-op on every call.
    """
    api_key = current_app.config.get('BREVO_API_KEY')
    sender  = current_app.config.get('MAIL_DEFAULT_SENDER', 'WorkPro <noreply@workpro.app>')

    if '<' in sender and '>' in sender:
        sender_name  = sender.split('<')[0].strip()
        sender_email = sender.split('<')[1].split('>')[0].strip()
    else:
        sender_name  = current_app.config.get('APP_NAME', 'WorkPro')
        sender_email = sender

    if not api_key:
        current_app.logger.warning(
            'Email not sent to %s (BREVO_API_KEY not configured). subject=%s', to, subject
        )
        return

    try:
        import requests
        resp = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            json={
                'sender':      {'name': sender_name, 'email': sender_email},
                'to':          [{'email': to}],
                'subject':     subject,
                'htmlContent': body_html,
            },
            headers={
                'accept':       'application/json',
                'api-key':      api_key,
                'content-type': 'application/json',
            },
            timeout=10,
        )
        if resp.status_code >= 300:
            current_app.logger.warning(
                'Brevo send failed (%s) to %s: %s', resp.status_code, to, resp.text[:200]
            )
        else:
            current_app.logger.info('Email sent to %s — %s', to, subject)
    except Exception as exc:
        current_app.logger.warning('Email not sent to %s (%s).', to, exc)


# ── Due-date reminders ────────────────────────────────────────────────────────

REMINDER_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f4f4f4;padding:24px">
<div style="max-width:520px;margin:auto;background:#fff;border-radius:12px;padding:28px">
  <h2 style="color:#7c6aff;margin-top:0">📋 Task Reminder — WorkPro</h2>
  <p>Hi {{ name }}, you have <strong>{{ count }} task{{ 's' if count != 1 else '' }}</strong>
     due <strong>{{ when }}</strong>:</p>
  <ul>
    {% for t in tasks %}
    <li style="margin-bottom:8px">
      <strong>{{ t.title }}</strong>
      {% if t.priority == 'high' %}<span style="color:#f87171"> 🔴 High</span>{% endif %}
      {% if t.category %} · <em>{{ t.category }}</em>{% endif %}
    </li>
    {% endfor %}
  </ul>
  <a href="{{ app_url }}/tasks" style="display:inline-block;margin-top:16px;padding:10px 20px;
     background:#7c6aff;color:#fff;border-radius:8px;text-decoration:none">Open WorkPro →</a>
  <p style="font-size:11px;color:#aaa;margin-top:24px">
    You're receiving this because task reminders are enabled in your WorkPro profile.
    <a href="{{ app_url }}/profile">Unsubscribe</a>
  </p>
</div>
</body>
</html>
"""

def send_due_reminders():
    """
    Send reminder emails for tasks due today or tomorrow.
    Call this once daily (e.g. 08:00 local time).
    """
    from app.models.user import User
    from app.models.task import Task
    from jinja2 import Template

    today    = date.today()
    tomorrow = today + timedelta(days=1)
    app_url  = current_app.config.get('APP_URL', 'https://workpro.app')

    users = User.query.filter_by(is_active=True, is_verified=True, email_reminders=True).all()
    sent  = 0
    for user in users:
        for when_label, due in [('today', today), ('tomorrow', tomorrow)]:
            tasks = Task.query.filter_by(user_id=user.id)\
                              .filter(Task.due_date == due)\
                              .filter(Task.status != 'done').all()
            if not tasks:
                continue
            body = Template(REMINDER_TEMPLATE).render(
                name=user.first_name, count=len(tasks),
                when=when_label, tasks=tasks, app_url=app_url,
            )
            _send_email(
                user.email,
                f'WorkPro: {len(tasks)} task{"s" if len(tasks)!=1 else ""} due {when_label}',
                body,
            )
            sent += 1
    current_app.logger.info('Due-reminder run complete — %d emails sent', sent)
    return sent


# ── Daily digest ──────────────────────────────────────────────────────────────

DIGEST_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f4f4f4;padding:24px">
<div style="max-width:540px;margin:auto;background:#fff;border-radius:12px;padding:28px">
  <h2 style="color:#7c6aff;margin-top:0">☀️ Good morning, {{ name }}!</h2>
  <p>Here's your WorkPro snapshot for today:</p>

  <div style="background:#f8f7ff;border-radius:8px;padding:16px;margin-bottom:16px">
    <strong>📊 Task overview</strong><br>
    <span style="color:#60a5fa">● {{ todo }} pending</span> &nbsp;
    <span style="color:#fbbf24">● {{ in_progress }} in progress</span> &nbsp;
    <span style="color:#27c98a">● {{ done }} done</span>
  </div>

  {% if due_today %}
  <p><strong>📅 Due today ({{ due_today|length }})</strong></p>
  <ul>{% for t in due_today %}<li>{{ t.title }}</li>{% endfor %}</ul>
  {% endif %}

  {% if streak > 1 %}
  <p>🔥 You're on a <strong>{{ streak }}-day streak</strong>! Keep it going.</p>
  {% endif %}

  <a href="{{ app_url }}/ai?service=plan_day"
     style="display:inline-block;margin-top:8px;padding:10px 20px;
     background:#7c6aff;color:#fff;border-radius:8px;text-decoration:none">
     Let AI plan my day →</a>

  <p style="font-size:11px;color:#aaa;margin-top:24px">
    <a href="{{ app_url }}/profile">Manage email preferences</a>
  </p>
</div>
</body>
</html>
"""

def send_daily_digest():
    """Send morning digest to all active users who have email reminders on."""
    from app.models.user import User
    from app.models.task import Task
    from jinja2 import Template

    today   = date.today()
    app_url = current_app.config.get('APP_URL', 'https://workpro.app')

    users = User.query.filter_by(is_active=True, is_verified=True, email_reminders=True).all()
    sent  = 0
    for user in users:
        stats = {
            'todo':        Task.query.filter_by(user_id=user.id, status='todo').count(),
            'in_progress': Task.query.filter_by(user_id=user.id, status='in_progress').count(),
            'done':        Task.query.filter_by(user_id=user.id, status='done').count(),
        }
        due_today = Task.query.filter_by(user_id=user.id)\
                              .filter(Task.due_date == today)\
                              .filter(Task.status != 'done').all()

        # Only send if user has anything going on
        if stats['todo'] + stats['in_progress'] + len(due_today) == 0:
            continue

        body = Template(DIGEST_TEMPLATE).render(
            name=user.first_name,
            streak=user.streak_days or 0,
            due_today=due_today,
            app_url=app_url,
            **stats,
        )
        _send_email(user.email, 'WorkPro — Your daily snapshot', body)
        sent += 1

    current_app.logger.info('Daily digest run — %d emails sent', sent)
    return sent


# ── Recurring task spawner ────────────────────────────────────────────────────

def spawn_recurring_tasks():
    """
    For every task with recur_type set, create a fresh copy for today
    if one doesn't already exist.  Run once per day at midnight.
    """
    from app.models.task import Task
    from app import db

    today     = date.today()
    weekday   = today.weekday()   # 0=Mon … 6=Sun
    month_day = today.day

    templates = Task.query.filter(Task.recur_type.isnot(None)).all()
    created   = 0
    for tmpl in templates:
        should_spawn = False
        if tmpl.recur_type == 'daily':
            should_spawn = True
        elif tmpl.recur_type == 'weekly' and tmpl.recur_day == weekday:
            should_spawn = True
        elif tmpl.recur_type == 'monthly' and tmpl.recur_day == month_day:
            should_spawn = True

        if not should_spawn:
            continue

        # Avoid duplicate if already spawned today
        exists = Task.query.filter_by(
            user_id=tmpl.user_id, title=tmpl.title, due_date=today,
        ).first()
        if exists:
            continue

        new_task = Task(
            title=tmpl.title,
            description=tmpl.description,
            priority=tmpl.priority,
            status='todo',
            category=tmpl.category,
            due_date=today,
            user_id=tmpl.user_id,
            assigned_to=tmpl.assigned_to,
            # Don't carry recur fields — child tasks are one-offs
        )
        db.session.add(new_task)
        created += 1

    db.session.commit()
    current_app.logger.info('Recurring task spawn — %d tasks created', created)
    return created


# ── Flask CLI commands ────────────────────────────────────────────────────────

def register_notify_commands(app):
    """Call from create_app() to add 'flask notify ...' commands."""

    @app.cli.group()
    def notify():
        """Notification & scheduling commands."""
        pass

    @notify.command('send-reminders')
    @with_appcontext
    def cmd_reminders():
        """Send due-date reminder emails."""
        n = send_due_reminders()
        click.echo(f'{n} reminder email(s) sent.')

    @notify.command('daily-digest')
    @with_appcontext
    def cmd_digest():
        """Send daily digest emails."""
        n = send_daily_digest()
        click.echo(f'{n} digest email(s) sent.')

    @notify.command('spawn-recurring')
    @with_appcontext
    def cmd_spawn():
        """Spawn recurring tasks for today."""
        n = spawn_recurring_tasks()
        click.echo(f'{n} recurring task(s) created.')
