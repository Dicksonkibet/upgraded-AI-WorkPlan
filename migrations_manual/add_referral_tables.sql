-- Run this once on your existing database to add referral features
-- Safe to run multiple times (uses IF NOT EXISTS)

-- Referral codes (one per user)
CREATE TABLE IF NOT EXISTS referral_codes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL UNIQUE REFERENCES users(id),
    code       VARCHAR(12) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_referral_codes_code ON referral_codes(code);

-- Signup tracking
CREATE TABLE IF NOT EXISTS referral_signups (
    id               SERIAL PRIMARY KEY,
    referral_code_id INTEGER NOT NULL REFERENCES referral_codes(id),
    referred_user_id INTEGER NOT NULL REFERENCES users(id),
    converted        BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMP DEFAULT NOW(),
    converted_at     TIMESTAMP
);

-- Commission ledger
CREATE TABLE IF NOT EXISTS commissions (
    id               SERIAL PRIMARY KEY,
    referral_code_id INTEGER NOT NULL REFERENCES referral_codes(id),
    referrer_id      INTEGER NOT NULL REFERENCES users(id),
    referred_user_id INTEGER NOT NULL REFERENCES users(id),
    payment_id       INTEGER NOT NULL REFERENCES payments(id),
    amount           FLOAT NOT NULL,
    rate             FLOAT NOT NULL,
    status           VARCHAR(20) DEFAULT 'pending',
    mpesa_receipt    VARCHAR(100),
    phone_number     VARCHAR(20),
    created_at       TIMESTAMP DEFAULT NOW(),
    paid_at          TIMESTAMP,
    notes            VARCHAR(255)
);

-- Add phone column to users if missing
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Add new system settings
INSERT INTO system_settings (key, value) VALUES ('commission_rate', '20')
    ON CONFLICT (key) DO NOTHING;
INSERT INTO system_settings (key, value) VALUES ('whatsapp_support', '')
    ON CONFLICT (key) DO NOTHING;

COMMIT;
