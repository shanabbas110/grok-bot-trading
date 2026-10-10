import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "trading",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "grokbot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "grokbot.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    import re

    m = re.match(
        r"postgres(?:ql)?://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/(?P<name>.+)",
        DATABASE_URL,
    )
    if m:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": m.group("name"),
                "USER": m.group("user"),
                "PASSWORD": m.group("password"),
                "HOST": m.group("host"),
                "PORT": m.group("port"),
            }
        }
    else:
        DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "run-agents-tick": {
        "task": "trading.tasks.run_all_agents_tick",
        "schedule": float(os.environ.get("AGENT_TICK_SECONDS", "30")),
    },
    "scan-markets": {
        "task": "trading.tasks.scan_markets",
        "schedule": 120.0,
    },
    "paper-position-maintenance": {
        "task": "trading.tasks.maintain_paper_positions",
        "schedule": 15.0,
    },
}

# App config
PAPER_MODE = os.environ.get("PAPER_MODE", "1") == "1"
PAPER_STARTING_BALANCE = float(os.environ.get("PAPER_STARTING_BALANCE", "1000"))
PAPER_FEE_BPS = int(os.environ.get("PAPER_FEE_BPS", "30"))
PAPER_SLIPPAGE_BPS = int(os.environ.get("PAPER_SLIPPAGE_BPS", "50"))

XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-3-mini")

SCAN_MIN_LIQUIDITY_USD = float(os.environ.get("SCAN_MIN_LIQUIDITY_USD", "50000"))
SCAN_MIN_VOLUME_24H = float(os.environ.get("SCAN_MIN_VOLUME_24H", "10000"))
SCAN_MIN_BUY_SELL_RATIO = float(os.environ.get("SCAN_MIN_BUY_SELL_RATIO", "1.1"))
SCAN_MAX_PAIR_AGE_HOURS = float(os.environ.get("SCAN_MAX_PAIR_AGE_HOURS", "72"))
SCAN_MAX_FDV_LIQUIDITY_RATIO = float(os.environ.get("SCAN_MAX_FDV_LIQUIDITY_RATIO", "50"))

RISK_MAX_POSITION_PCT = float(os.environ.get("RISK_MAX_POSITION_PCT", "15"))
RISK_MAX_OPEN_POSITIONS = int(os.environ.get("RISK_MAX_OPEN_POSITIONS", "5"))
RISK_DAILY_LOSS_KILL_PCT = float(os.environ.get("RISK_DAILY_LOSS_KILL_PCT", "10"))
RISK_MAX_TRADES_PER_HOUR = int(os.environ.get("RISK_MAX_TRADES_PER_HOUR", "20"))
RISK_MIN_CONFIDENCE = float(os.environ.get("RISK_MIN_CONFIDENCE", "0.62"))
RISK_MANDATORY_SL_TP = os.environ.get("RISK_MANDATORY_SL_TP", "1") == "1"

# Jev / TypeSafe decision gate
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
JEV_MODEL = os.environ.get("JEV_MODEL", "jev-1.13.0")
JEV_TIMEOUT_SECONDS = float(os.environ.get("JEV_TIMEOUT_SECONDS", "30"))
JEV_BUY_CONFIDENCE_THRESHOLD = float(os.environ.get("JEV_BUY_CONFIDENCE_THRESHOLD", "0.72"))
JEV_EXIT_CONFIDENCE_THRESHOLD = float(os.environ.get("JEV_EXIT_CONFIDENCE_THRESHOLD", "0.6"))
JEV_EXIT_NOUL_THRESHOLD = float(os.environ.get("JEV_EXIT_NOUL_THRESHOLD", "0.65"))

# jev+grok | grok-only | jev-only | mock
DECIDER_MODE = os.environ.get("DECIDER_MODE", "jev+grok")
GROK_MIN_CONFIDENCE = float(os.environ.get("GROK_MIN_CONFIDENCE", "0.65"))

DEFAULT_STOP_LOSS_PCT = float(os.environ.get("DEFAULT_STOP_LOSS_PCT", "3.0"))
DEFAULT_TAKE_PROFIT_PCT = float(os.environ.get("DEFAULT_TAKE_PROFIT_PCT", "4.5"))
DEFAULT_POSITION_SIZE_PCT = float(os.environ.get("DEFAULT_POSITION_SIZE_PCT", "6.0"))
MAX_TAKE_PROFIT_PCT = float(os.environ.get("MAX_TAKE_PROFIT_PCT", "6.0"))
MAX_STOP_LOSS_PCT = float(os.environ.get("MAX_STOP_LOSS_PCT", "4.0"))
PAPER_POSITION_TIMEOUT_HOURS = float(os.environ.get("PAPER_POSITION_TIMEOUT_HOURS", "1.5"))

WIN_RATE_TARGET_WINS = int(os.environ.get("WIN_RATE_TARGET_WINS", "50"))
WIN_RATE_TARGET_CLOSED = int(os.environ.get("WIN_RATE_TARGET_CLOSED", "60"))

TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
JEV_TIMEOUT_SECONDS = float(os.environ.get("JEV_TIMEOUT_SECONDS", "30"))
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL_SECONDS", "120"))
DAILY_TARGET_PCT = float(os.environ.get("DAILY_TARGET_PCT", "15"))
CHAINS_TO_SCAN = os.environ.get("CHAINS_TO_SCAN", "solana,ethereum,base,bsc")
RUG_CHECK_ENABLED = os.environ.get("RUG_CHECK_ENABLED", "1") == "1"
RUG_DEV_WALLET_PCT_MAX = float(os.environ.get("RUG_DEV_WALLET_PCT_MAX", "0.12"))
