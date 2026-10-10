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
RISK_MIN_CONFIDENCE = float(os.environ.get("RISK_MIN_CONFIDENCE", "0.55"))
RISK_MANDATORY_SL_TP = os.environ.get("RISK_MANDATORY_SL_TP", "1") == "1"
