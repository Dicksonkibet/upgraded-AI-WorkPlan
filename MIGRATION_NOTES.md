# WorkPro — Improvement Migration Notes

## New database columns (run `flask db migrate && flask db upgrade`)

### `users` table
| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `onboarding_done` | Boolean | False | Hides onboarding checklist once dismissed |
| `email_reminders` | Boolean | True | User opt-in for due-date & digest emails |
| `streak_days` | Integer | 0 | Consecutive days with a completed task |
| `streak_last_active` | Date | NULL | Date of last streak increment |

### `tasks` table
| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `recur_type` | String(20) | NULL | `'daily'`, `'weekly'`, or `'monthly'` |
| `recur_day` | Integer | NULL | For weekly: 0–6 (Mon–Sun). For monthly: 1–31 |

## New files added
- `app/services/notification_service.py` — email reminders, digest, recurring task spawner
- `MIGRATION_NOTES.md` — this file

## Changed files
- `app/models/user.py` — added 4 new columns + `update_streak()` + `onboarding_done`
- `app/models/task.py` — added `recur_type`, `recur_day` columns
- `app/views/__init__.py` — added `/onboarding/dismiss` route; streak update on task complete
- `app/__init__.py` — registers `flask notify` CLI commands
- `templates/dashboard/index.html` — embedded AI command bar, overdue nudge, onboarding checklist, streak badge
- `requirements.txt` — added `Flask-Mail>=0.9.1`

## Setting up email reminders
1. Add to your `.env`:
   ```
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your@email.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=noreply@workpro.app
   APP_URL=https://your-domain.com
   ```
2. Init Flask-Mail in `app/__init__.py`:
   ```python
   from flask_mail import Mail
   mail = Mail()
   mail.init_app(app)
   ```
3. Add a cron job (or APScheduler):
   ```bash
   # 08:00 daily
   flask notify send-reminders
   flask notify daily-digest
   # midnight daily
   flask notify spawn-recurring
   ```

## Setting up recurring tasks (UI)
The `recur_type` and `recur_day` fields are on the Task model. 
To expose them in the task creation form, add these fields to `templates/tasks/index.html`
in the create-task modal:
```html
<select name="recur_type">
  <option value="">No repeat</option>
  <option value="daily">Daily</option>
  <option value="weekly">Weekly</option>
  <option value="monthly">Monthly</option>
</select>
<input type="number" name="recur_day" min="0" max="31"
       placeholder="Day (0=Mon for weekly, 1-31 for monthly)">
```
