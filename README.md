# WorkPro — Smart Company Management Platform

A professional Flask-based company management system with **subscription tiers**, **M-Pesa payments**, **AI assistant with full system management**, role-based permissions, and a clean light-mode UI.

---

## ✨ What's New (Updated Version)

### 🔐 Subscription Management
- **Free plan**: 20 tasks, 10 documents, 5 AI messages/day
- **Pro plan**: Unlimited everything + full AI management
- Usage meters on dashboard and task/doc pages
- Feature gates enforced server-side and client-side

### 📱 M-Pesa Payments (Safaricom Daraja API)
- STK Push to user's phone for seamless payment
- Monthly (KES 999) and Annual (KES 8,999) billing
- Webhook callback auto-activates subscription
- Polling endpoint for real-time payment status
- Full billing history

### 🤖 AI System Management
- AI connects to all API endpoints (`/api/v1/tasks`, `/api/v1/plans`, `/api/v1/documents`)
- Creates, updates, and deletes data on behalf of the logged-in user
- Respects role permissions — cannot exceed user's own access level
- Asks for confirmation before destructive (delete) actions
- Free users: read-only AI · Pro users: full management
- Daily message limits enforced for free tier

### 🎨 Redesigned Landing Page
- Professional light-mode design
- Hero, features grid, AI demo, pricing table, testimonials
- M-Pesa payment badge on Pro pricing card
- Fully responsive (mobile-first)

### ⚡ Performance & UX
- Optimistic UI updates for task status changes
- Flask-Caching for API responses
- Toast notifications for all actions
- Responsive sidebar with mobile overlay
- Smooth fade-in animations

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
cd workpro
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values (see configuration section below)
```

### 3. Run
```bash
python app.py
```
Visit **http://localhost:5000**

### Default Admin Account
- Email: `admin@workpro.app`
- Password: `Admin@1234`
- Plan: Pro (set automatically on first run)

---

## ⚙️ Configuration

### Required
| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask secret key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | SQLite (dev) or PostgreSQL URL |
| `GROQ_API_KEY` | Groq API key from https://console.groq.com |

### M-Pesa (for Pro subscriptions)
| Variable | Description |
|---|---|
| `MPESA_ENV` | `sandbox` or `production` |
| `MPESA_CONSUMER_KEY` | From Safaricom Developer Portal |
| `MPESA_CONSUMER_SECRET` | From Safaricom Developer Portal |
| `MPESA_PASSKEY` | Lipa Na M-Pesa passkey |
| `MPESA_SHORTCODE` | Your business shortcode (174379 for sandbox) |
| `MPESA_CALLBACK_URL` | Public HTTPS URL for payment confirmation |

> **Local M-Pesa testing**: Use [ngrok](https://ngrok.com) to expose your local server:
> ```bash
> ngrok http 5000
> # Copy the HTTPS URL to MPESA_CALLBACK_URL in .env
> ```

### Subscription Pricing
```env
PRO_MONTHLY_PRICE=999     # KES per month
PRO_ANNUAL_PRICE=8999     # KES per year
FREE_TASKS_LIMIT=20
FREE_DOCS_LIMIT=10
FREE_AI_MSG_LIMIT=5
```

---

## 🏗️ Architecture

```
workpro/
├── app.py                    # Entry point
├── config.py                 # Environment configurations
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py           # App factory, extensions
│   ├── models/
│   │   ├── user.py           # User model with subscription helpers
│   │   ├── role.py           # Role & Permission models
│   │   ├── task.py           # Task, DailyPlan, Document, ActivityLog
│   │   └── subscription.py   # Subscription, Payment, AIUsage
│   ├── services/
│   │   ├── ai_service.py     # AI with full API access & action execution
│   │   ├── auth_service.py   # Auth & email verification
│   │   ├── data_services.py  # Task, Plan, Doc CRUD
│   │   ├── user_service.py   # User management
│   │   └── subscription_service.py  # M-Pesa + subscription management
│   ├── views/
│   │   ├── __init__.py       # All page blueprints
│   │   ├── auth.py           # Login, register, password reset
│   │   ├── landing.py        # Landing page
│   │   └── subscription.py   # Subscription management & M-Pesa
│   ├── api/
│   │   └── __init__.py       # REST API v1 (all endpoints)
│   └── utils/
│       ├── decorators.py     # Permission, admin, pro decorators
│       └── seeder.py         # Default roles, permissions, admin user
└── templates/
    ├── base.html             # Light-mode base layout
    ├── landing.html          # Public landing page
    ├── dashboard/            # Dashboard, logs, profile
    ├── tasks/                # Task management
    ├── planner/              # Daily planner
    ├── docs/                 # Documentation
    ├── ai/                   # AI chat
    ├── subscription/         # Plan management & M-Pesa upgrade
    ├── admin/                # Admin panel
    ├── users/                # User management
    └── auth/                 # Login, register, reset
```

---

## 🔌 API Endpoints

All endpoints require authentication (session or JWT).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/me` | Current user + limits + usage |
| GET | `/api/v1/tasks` | List tasks (filters: status, priority, q) |
| POST | `/api/v1/tasks` | Create task (checks free limit) |
| PUT | `/api/v1/tasks/<id>` | Update task |
| DELETE | `/api/v1/tasks/<id>` | Delete task |
| GET | `/api/v1/plans?date=YYYY-MM-DD` | Get plans for date |
| POST | `/api/v1/plans` | Create plan |
| PUT | `/api/v1/plans/<id>` | Update plan |
| DELETE | `/api/v1/plans/<id>` | Delete plan |
| GET | `/api/v1/documents` | List documents |
| POST | `/api/v1/documents` | Create document (checks free limit) |
| PUT | `/api/v1/documents/<id>` | Update document |
| DELETE | `/api/v1/documents/<id>` | Delete document |
| GET | `/api/v1/logs` | Recent activity logs |
| GET | `/api/v1/subscription` | Subscription status |
| POST | `/subscription/initiate` | Start M-Pesa payment |
| GET | `/subscription/poll/<id>` | Check payment status |
| POST | `/subscription/mpesa-callback` | M-Pesa webhook |

---

## 🤖 AI Capabilities by Plan

| Feature | Free | Pro |
|---|---|---|
| Chat messages | 5/day | Unlimited |
| Read tasks/plans/docs | ✓ | ✓ |
| Create tasks via chat | ✗ | ✓ |
| Update tasks via chat | ✗ | ✓ |
| Delete tasks via chat | ✗ | ✓ (with confirmation) |
| Create plans via chat | ✗ | ✓ |
| Create documents via chat | ✗ | ✓ |
| Generate documents | ✗ | ✓ |
| Task summary | ✓ | ✓ |
| Day planning suggestion | ✓ | ✓ |

---

## 📦 Production Deployment

```bash
# Install gunicorn
pip install gunicorn

# Set environment
export FLASK_ENV=production
export DATABASE_URL=postgresql://user:pass@host/workpro

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or with systemd service (recommended)
# See deployment documentation
```

---

## 🛡️ Security Notes

- CSRF protection on all forms (Flask-WTF)
- Passwords hashed with bcrypt
- Permission checks on every route and API endpoint
- Subscription limits enforced server-side (cannot be bypassed client-side)
- M-Pesa callback validated before activating subscription
- SQL injection protection via SQLAlchemy ORM

---

*Built with Flask · SQLAlchemy · Groq AI · Safaricom Daraja API*
