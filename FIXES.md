# Fix Log — WorkPro Health Check

Ran the app end-to-end (boot, every page, every CRUD flow, auth flows, API)
in a clean venv rather than just reading the code. Found and fixed the
following — all confirmed broken before, confirmed working after.

## Crashes (would 500 in production)

1. **AI chat / report / summarize / suggest-plan crashed for every free-tier
   user.** `User.get_limits()` looked up the settings key `free_ai_msgs_limit`,
   but the settings schema (and the admin UI) define it as `free_ai_msg_limit`
   (no "s"). The mismatch made the limit resolve to `''`, and
   `can_use_ai()` then compared `int < str`, raising `TypeError`. Invisible
   in testing because admin/Pro accounts skip this check entirely.
   → `app/models/user.py`

2. **`GET /api/v1/me` always crashed.** It called `current_user.to_dict()`,
   but `User` never defined that method (every other model — Task, Document,
   Role, Subscription — does). Added a `to_dict()` to `User`.
   → `app/models/user.py`

3. **Password reset was completely broken.** `auth_service.reset_password()`
   called `user.invalidate_reset_token()`, which didn't exist anywhere.
   Every reset attempt raised `AttributeError`.
   → `app/models/user.py`

4. **Email verification was completely broken.** Same issue:
   `user.invalidate_verify_token()` didn't exist. New users could never
   verify their email — and since login blocks unverified accounts, they
   could never log in at all. This only didn't show up in testing because
   the seeded admin account is pre-verified.
   → `app/models/user.py`

## Silent failures / dead UI

5. **Onboarding "dismiss" button always 404'd.** The JS called
   `/onboarding/dismiss`, but that route is registered under the
   `/dashboard` blueprint prefix (`/dashboard/onboarding/dismiss`).
   → `templates/dashboard/index.html`

6. **A whole block of dashboard JS never ran.** The `extra_head` block had
   `<script src="...chart.umd.js">...inline JS...</script>` — per the HTML
   spec, a `<script>` tag with a `src` attribute ignores any inline content
   between its tags. The AI command bar / reschedule / onboarding-dismiss
   logic defined there was 100% dead code; a working duplicate already
   existed in the `extra_js` block at the bottom of the same file. Removed
   the dead duplicate.
   → `templates/dashboard/index.html`

7. **Reminder & daily-digest emails (`flask notify ...`) silently never
   sent.** `notification_service.py` still used Flask-Mail, but Flask-Mail
   is never initialized anywhere in the app (`auth_service.py` already
   migrated to Brevo's HTTP API for the same reason — Render blocks SMTP
   ports). Switched `_send_email()` to Brevo, matching `auth_service.py`.
   → `app/services/notification_service.py`

8. **`manager_required` decorator would crash if ever used.** It called
   `current_user.is_manager()`, which didn't exist, even though "manager"
   is a real seeded role. Currently dead code (not wired to any route), but
   fixed preemptively. Added `is_manager()` to `User`, mirroring `is_admin()`.
   → `app/models/user.py`

9. **Editing/deleting a stale or already-deleted task/document threw a raw
   404 page** instead of a friendly flash message, because
   `TaskService.get_by_id` / `DocumentService.get_by_id` used
   `Query.get_or_404()` outside a try/except. Switched to `Query.get()` +
   explicit `None` handling; the `docs.view` route now flashes "Document
   not found" and redirects instead of crashing into the global 404 page.
   API endpoints (`PUT /api/v1/tasks/<id>` etc.) now correctly return a JSON
   error instead of an HTML 404 page for the same case.
   → `app/services/data_services.py`, `app/views/__init__.py`

## Verified after fixing
- Fresh boot + seed on a clean SQLite DB
- All 12 main pages (dashboard, tasks, planner, docs, admin, users, ai,
  subscription, etc.) return 200 for an authenticated admin
- Register → verify-email → reset-password → login round-trip
- Task/plan/document create → edit → status update → delete
- `/api/v1/me`, `/api/v1/tasks`, `/api/v1/plans`, `/api/v1/documents`
- AI chat gracefully degrades to a friendly message when `GROQ_API_KEY`
  isn't set (no crash) — and no longer crashes for free-tier users at all

## Round 2 — reported via screenshot

10. **Raw CSS rendering as visible text at the top of the dashboard.**
    `dashboard/index.html` had two separate chunks of CSS, but only one
    pair of `<style>` tags wrapping them — a `</style>` closed the
    stylesheet early (right after the responsive media query), and the
    second chunk (AI command bar, onboarding checklist, overdue banner,
    streak badge rules) was left as bare text in the page body, with only
    a stray closing `</style>` and no matching open tag. Browsers render
    anything outside `<style>`/`<script>` as visible text, which is exactly
    the wall of CSS you saw above the AI command bar — and it's also why
    the onboarding checklist had no card background, numbered-circle
    badges, etc. (that CSS never applied). Removed the premature
    `</style>` so the whole thing is one continuous stylesheet.
    → `templates/dashboard/index.html`

    Verified: rendered the dashboard HTML and confirmed the AI-command-bar
    CSS now parses inside a `<style>` block and no longer appears as text
    in the page body.
