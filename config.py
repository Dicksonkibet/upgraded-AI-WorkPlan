import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class BaseConfig:
    SECRET_KEY               = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')
    JWT_SECRET_KEY           = os.getenv('JWT_SECRET_KEY', 'dev-jwt-key-change-in-prod')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED         = True
    APP_NAME                 = os.getenv('APP_NAME', 'WorkPro')
    FRONTEND_URL             = os.getenv('FRONTEND_URL', 'http://localhost:5000')

    # Mail — sent via Brevo's HTTP API (not SMTP). Render's free tier (and
    # some paid tiers) blocks outbound traffic on SMTP ports 25/465/587,
    # which caused smtplib to hang until gunicorn killed the worker
    # (WORKER TIMEOUT -> SIGKILL). Brevo's REST API is plain HTTPS on
    # port 443, which is never blocked.
    # Get the key from Brevo: Settings -> SMTP & API -> API Keys tab
    # (NOT the SMTP tab — that key won't work here).
    BREVO_API_KEY        = os.getenv('BREVO_API_KEY')
    MAIL_DEFAULT_SENDER  = os.getenv('MAIL_DEFAULT_SENDER', 'WorkPro <devkencompany@gmail.com>')

    # AI — Groq
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

    # M-Pesa / Daraja API
    MPESA_CONSUMER_KEY    = os.getenv('MPESA_CONSUMER_KEY', '')
    MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET', '')
    MPESA_PASSKEY         = os.getenv('MPESA_PASSKEY', '')
    MPESA_SHORTCODE       = os.getenv('MPESA_SHORTCODE', '174379')
    MPESA_ENV             = os.getenv('MPESA_ENV', 'sandbox')
    MPESA_CALLBACK_URL    = os.getenv('MPESA_CALLBACK_URL', 'https://yourdomain.com/subscription/mpesa-callback')

    # Subscription plans
    PRO_MONTHLY_PRICE    = int(os.getenv('PRO_MONTHLY_PRICE', 999))
    COMMISSION_RATE      = int(os.getenv('COMMISSION_RATE', 20))
    WHATSAPP_SUPPORT     = os.getenv('WHATSAPP_SUPPORT', '')
    MPESA_INITIATOR_NAME = os.getenv('MPESA_INITIATOR_NAME', 'testapi')
    MPESA_SECURITY_CREDENTIAL = os.getenv('MPESA_SECURITY_CREDENTIAL', '')
    PRO_ANNUAL_PRICE  = int(os.getenv('PRO_ANNUAL_PRICE', 8999))

    # Free plan limits
    FREE_TASKS_LIMIT  = 20
    FREE_DOCS_LIMIT   = 10
    FREE_AI_MSG_LIMIT = 5

    # Pagination
    ITEMS_PER_PAGE = 20

    # Cache
    CACHE_TYPE    = 'SimpleCache'
    CACHE_TIMEOUT = 300

    # SQLAlchemy connection pool
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle':  300,
        'pool_size':     3,
        'max_overflow':  2,
        'pool_timeout':  30,
        'connect_args': {
            'keepalives':          1,
            'keepalives_idle':     30,
            'keepalives_interval': 10,
            'keepalives_count':    5,
        }
    }


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI   = os.getenv('DATABASE_URL', 'sqlite:///workpro_dev.db')
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}


class ProductionConfig(BaseConfig):
    DEBUG            = False
    WTF_CSRF_ENABLED = True

    # Render gives 'postgres://' but SQLAlchemy requires 'postgresql://'
    _db_url = os.getenv('DATABASE_URL', '')
    SQLALCHEMY_DATABASE_URI = (
        _db_url.replace('postgres://', 'postgresql://', 1)
        if _db_url.startswith('postgres://')
        else _db_url
    )

    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size':   3,   # keep at 3 on Render free tier
        'max_overflow': 2,
    }


class TestingConfig(BaseConfig):
    TESTING          = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI   = os.getenv('TEST_DATABASE_URL', 'sqlite:///workpro_test.db')
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    # Note: there's no Brevo equivalent of MAIL_SUPPRESS_SEND. Tests should
    # mock the network call directly, e.g.:
    #   with mock.patch('app.services.auth_service.requests.post') as m:
    #       m.return_value.status_code = 201
    #       ...


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}