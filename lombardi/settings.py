"""Lombardi Saúde – Django production settings (secrets via environment)."""
import os
from pathlib import Path
from urllib.parse import urlsplit, unquote
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY and not DEBUG:
    raise ImproperlyConfigured("Configure DJANGO_SECRET_KEY antes de iniciar.")
if DEBUG and not SECRET_KEY:
    SECRET_KEY = "insecure-local-dev-only-not-for-production"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app").split(",") if s.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "clinic.apps.ClinicConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "clinic.middleware.MustChangePasswordMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "clinic.analytics_middleware.ConsentAnalyticsMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "lombardi.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
              "APP_DIRS": True, "OPTIONS": {"context_processors": [
                  "django.template.context_processors.debug", "django.template.context_processors.request",
                  "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
                  "clinic.context_processors.notification_bell", "clinic.admin_navigation.sidebar_context"]}}]
WSGI_APPLICATION = "lombardi.wsgi.application"
# Use a dedicated PostgreSQL database; do not touch the pre-existing Next.js tables.
DATABASE_URL = os.getenv("DJANGO_DATABASE_URL") or os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    parsed = urlsplit(DATABASE_URL)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ImproperlyConfigured("DATABASE_URL precisa ser PostgreSQL")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""), "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "", "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"sslmode": "require"},
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("POSTGRES_DB", "lombardi_saude"),
        "USER": os.getenv("POSTGRES_USER", "lombardi"), "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "db"), "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "disable")},
    }}
AUTH_USER_MODEL = "clinic.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "private_media"  # Only for local legacy usage; invoices stored in Postgres for Vercel.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/gestao/login/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 7 * 1024 * 1024
DEFAULT_FROM_EMAIL = "Lombardi Saúde <nao-responder@localhost>"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://lombardisaude.com.br").rstrip("/")
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
