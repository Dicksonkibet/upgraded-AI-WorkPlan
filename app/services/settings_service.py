from flask import current_app
from app import db
from app.models.settings import SystemSetting

# Schema for every setting the admin can edit from the UI.
# `config_key` is the .env / config.py fallback used until an admin
# overrides it from the Settings panel.
SETTINGS_SCHEMA = {
    'pro_monthly_price': {
        'label': 'Pro Monthly Price (KES)', 'type': int, 'config_key': 'PRO_MONTHLY_PRICE',
    },
    'commission_rate': {
        'label': 'Referral Commission Rate (%)', 'type': int, 'config_key': 'COMMISSION_RATE',
    },
    'whatsapp_support': {
        'label': 'WhatsApp Support Number', 'type': str, 'config_key': 'WHATSAPP_SUPPORT',
        'optional': True,
    },
    'pro_annual_price': {
        'label': 'Pro Annual Price (KES)', 'type': int, 'config_key': 'PRO_ANNUAL_PRICE',
    },
    'free_tasks_limit': {
        'label': 'Free Plan — Task Limit', 'type': int, 'config_key': 'FREE_TASKS_LIMIT',
    },
    'free_docs_limit': {
        'label': 'Free Plan — Document Limit', 'type': int, 'config_key': 'FREE_DOCS_LIMIT',
    },
    'free_ai_msg_limit': {
        'label': 'Free Plan — AI Messages / day', 'type': int, 'config_key': 'FREE_AI_MSG_LIMIT',
    },
    'mpesa_shortcode': {
        'label': 'M-Pesa Shortcode', 'type': str, 'config_key': 'MPESA_SHORTCODE',
    },
    'mpesa_callback_url': {
        'label': 'M-Pesa Callback URL', 'type': str, 'config_key': 'MPESA_CALLBACK_URL',
    },
    'mpesa_env': {
        'label': 'M-Pesa Environment', 'type': str, 'config_key': 'MPESA_ENV',
        'choices': ['sandbox', 'production'],
    },
    # ── AI Agent Configuration ──────────────────────────────────────
    'ai_persona_name': {
        'label': 'AI Agent Name', 'type': str, 'config_key': 'AI_PERSONA_NAME',
        'optional': True,
    },
    'ai_response_tone': {
        'label': 'AI Response Tone', 'type': str, 'config_key': 'AI_RESPONSE_TONE',
        'choices': ['professional', 'friendly', 'concise', 'formal', 'casual'],
        'optional': True,
    },
    'ai_intro_message': {
        'label': 'AI Intro Message', 'type': str, 'config_key': 'AI_INTRO_MESSAGE',
        'optional': True,
    },
    'ai_model': {
        'label': 'AI Model', 'type': str, 'config_key': 'AI_MODEL',
        'choices': ['llama-3.1-8b-instant', 'llama-3.3-70b-versatile',
                    'llama-3.1-70b-versatile', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
        'optional': True,
    },
    'ai_max_tokens': {
        'label': 'AI Max Tokens', 'type': int, 'config_key': 'AI_MAX_TOKENS',
        'optional': True,
    },
    'ai_temperature': {
        'label': 'AI Temperature', 'type': str, 'config_key': 'AI_TEMPERATURE',
        'optional': True,
    },
    'ai_trial_task_limit': {
        'label': 'AI Trial Task Limit', 'type': int, 'config_key': 'AI_TRIAL_TASK_LIMIT',
        'optional': True,
    },
    'pro_ai_msg_limit': {
        'label': 'Pro Plan AI Messages / day', 'type': int, 'config_key': 'PRO_AI_MSG_LIMIT',
        'optional': True,
    },
    'ai_access_level': {
        'label': 'AI Access Level', 'type': str, 'config_key': 'AI_ACCESS_LEVEL',
        'choices': ['all', 'pro_only', 'disabled'],
        'optional': True,
    },
}

# NOTE: M-Pesa secrets (MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET / MPESA_PASSKEY)
# and mail/Groq credentials are deliberately NOT included here — those stay in
# .env only, since putting API secrets in an admin-editable DB table/UI is a
# security smell (visible to anyone who can read the DB, easy to leak via XSS,
# no rotation/audit trail, etc).


class SettingsService:

    # Default values for AI settings not set by admin yet
    AI_DEFAULTS = {
        'ai_persona_name':    'WorkPro AI Agent',
        'ai_response_tone':   'professional',
        'ai_intro_message':   '',
        'ai_model':           'llama-3.1-8b-instant',
        'ai_max_tokens':      '1500',
        'ai_temperature':     '0.7',
        'ai_trial_task_limit': '20',
        'pro_ai_msg_limit':   '999',
        'ai_access_level':    'all',
    }

    def get(self, key):
        """Return the effective value for a single setting (DB override, else config/.env default)."""
        if key not in SETTINGS_SCHEMA:
            return self.AI_DEFAULTS.get(key, '')
        meta = SETTINGS_SCHEMA[key]
        row  = SystemSetting.query.filter_by(key=key).first()
        raw  = row.value if (row and row.value not in (None, '')) else (
            current_app.config.get(meta['config_key']) or self.AI_DEFAULTS.get(key)
        )
        try:
            return meta['type'](raw)
        except (TypeError, ValueError):
            return raw

    def get_all(self):
        """Return {key: effective_value} for every setting — used to populate the Settings form."""
        result = {key: self.get(key) for key in SETTINGS_SCHEMA}
        # Expose AI defaults as well for template access via settings.get(...)
        for k, v in self.AI_DEFAULTS.items():
            if k not in result:
                result[k] = self.get(k)
        return result

    def update(self, form_data: dict):
        """Validate + persist any settings present in form_data. Returns a dict of {key: error_message}."""
        errors = {}
        to_save = {}

        for key, meta in SETTINGS_SCHEMA.items():
            if key not in form_data:
                continue
            raw = (form_data[key] or '').strip()

            is_optional = meta.get('optional', False)
            if meta['type'] is int:
                if not raw.isdigit():
                    if is_optional and not raw:
                        continue  # skip optional empty int fields
                    errors[key] = f"{meta['label']} must be a positive whole number."
                    continue
                value = str(int(raw))
            else:
                if meta.get('choices') and raw not in meta['choices']:
                    if is_optional and not raw:
                        continue
                    errors[key] = f"{meta['label']} must be one of: {', '.join(meta['choices'])}."
                    continue
                if not raw and not is_optional:
                    errors[key] = f"{meta['label']} cannot be empty."
                    continue
                value = raw

            to_save[key] = value

        if errors:
            return errors  # nothing is saved if anything failed validation

        for key, value in to_save.items():
            row = SystemSetting.query.filter_by(key=key).first()
            if row:
                row.value = value
            else:
                db.session.add(SystemSetting(key=key, value=value))
        db.session.commit()
        return {}


settings_service = SettingsService()
