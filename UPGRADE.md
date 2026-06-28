# WorkPro Production Upgrade Guide

This version adds **Referral & Commission system**, **WhatsApp Help support**, 
and **Admin-configurable payout settings** on top of the existing M-Pesa subscription stack.

---

## What's New

### 🤝 Referral Program (`/referral/`)
- Every user gets a unique referral link automatically
- Referred signups are tracked in the database
- When a referred user pays for Pro, the referrer earns a commission (default 20%)
- Commission is auto-sent to the referrer's M-Pesa via B2C API
- If B2C fails (phone not set, API error), the commission stays "pending" for manual admin payout

### 💰 Commission Auto-Payouts
- Triggered instantly when `subscription_service.confirm_payment()` runs
- Uses M-Pesa B2C (`/mpesa/b2c/v1/paymentrequest`)
- Requires `MPESA_INITIATOR_NAME` and `MPESA_SECURITY_CREDENTIAL` in your .env
- Admin can manually mark commissions as paid at `/referral/admin`

### ❓ Help & Support Page (`/help/`)
- FAQ accordion covering all common questions
- WhatsApp button linked to your support number (set in Admin Panel)
- Email fallback link

### ⚙️ New Admin Panel Settings
- **Referral Commission Rate (%)** — default 20
- **WhatsApp Support Number** — international format (e.g. 254712345678)

---

## Deployment Steps

### 1. Fresh deployment (new database)
The app runs `db.create_all()` on startup — all new tables are created automatically.

### 2. Existing database (already deployed)
Run the migration script:
```bash
psql $DATABASE_URL < migrations_manual/add_referral_tables.sql
```

### 3. New environment variables
Add these to your `.env` / Render environment:
```
MPESA_INITIATOR_NAME=your-initiator-name
MPESA_SECURITY_CREDENTIAL=your-b2c-security-credential
COMMISSION_RATE=20
WHATSAPP_SUPPORT=254712345678
```

> **Note:** `COMMISSION_RATE` and `WHATSAPP_SUPPORT` can also be changed live 
> from the Admin Panel without redeploying.

### 4. M-Pesa B2C Setup (for auto payouts)
1. Log into the Safaricom Daraja portal
2. Go to **My Apps** → your app → **B2C** tab
3. Set your Result URL to: `https://yourdomain.com/subscription/mpesa-callback/b2c-result`
4. Copy your **Initiator Name** and generate a **Security Credential**
5. Add both to your environment variables

> Without B2C credentials, commissions still work — they'll just stay "pending" 
> until you manually mark them paid in the Admin Panel.

---

## Security Notes
- Referral codes are cryptographically random (via `secrets.token_urlsafe`)
- Self-referral is blocked server-side
- Double-commission is blocked (only first payment per referred user counts)
- All new routes are behind `@login_required`; admin routes behind `@admin_required`
- CSRF protection on all POST forms

---

## Default Admin
- Email: `admin@workpro.app`  
- Password: `Admin@1234`  
- **Change this immediately after first login.**
