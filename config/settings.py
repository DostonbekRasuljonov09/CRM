"""
O'quv markazlari CRM - Django sozlamalari (0-bosqich).

Maxfiy qiymatlar .env fayldan o'qiladi (python-dotenv).
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """.env dagi matnni bool ga aylantiradi."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "ha")


def env_int(name, default):
    """.env dagi matnni butun songa aylantiradi."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def env_list(name, default=""):
    """Vergul bilan ajratilgan qiymatlarni ro'yxatga aylantiradi."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Asosiy ---

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY topilmadi. .env.example dan .env fayl yarating."
    )

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")


# --- Ilovalar ---

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.common",
    "apps.accounts",
    "apps.centers",
    "apps.audit",
    "apps.courses",
    "apps.students",
    "apps.study_groups",
    "apps.lessons",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Baza (PostgreSQL) ---

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "crm"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Foydalanuvchi ---

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- DRF va JWT ---

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # services.py dagi Django ValidationError -> 400
    "EXCEPTION_HANDLER": "apps.common.exceptions.crm_exception_handler",
    # Ro'yxatlar sahifalanadi: /api/lessons/ bir markazda minglab yozuv bo'ladi
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Login'ni brute-force qilishga qarshi
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
    # Mijoz IP'si qaysi manbadan olinadi.
    # 0  - faqat REMOTE_ADDR (proxy yo'q). Mijoz yuborgan X-Forwarded-For
    #      e'tiborsiz qoldiriladi, aks holda har safar boshqa soxta IP
    #      yuborib tezlik cheklovini aylanib o'tish mumkin.
    # 1  - bitta ishonchli proxy ortida (masalan nginx)
    "NUM_PROXIES": env_int("NUM_PROXIES", 0),
}

SIMPLE_JWT = {
    # Qisqa muddat: o'g'irlangan token uzoq ishlamasin
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # Yangilashda eski refresh token qora ro'yxatga tushadi
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}


# --- Til va vaqt ---

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True


# --- Statik fayllar ---

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- Xavfsizlik (DEBUG=False bo'lganda) ---

# HTTPS orqali ishlaganda .env da SECURE_HTTPS=True qiling
SECURE_HTTPS = env_bool("SECURE_HTTPS", False)

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = SECURE_HTTPS
    CSRF_COOKIE_SECURE = SECURE_HTTPS
    SECURE_SSL_REDIRECT = SECURE_HTTPS

    if SECURE_HTTPS:
        SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)  # 1 yil
        # Bu ikkalasi ataylab standart holda o'chiq:
        # - INCLUDE_SUBDOMAINS: markazlar uchun subdomen rejasi bor
        #   (Center.slug), barcha subdomenlarni HTTPS ga majburlashdan oldin
        #   ularning sertifikati tayyor bo'lishi kerak
        # - PRELOAD: brauzerlar ro'yxatiga tushgandan keyin qaytarish
        #   oylar oladi - bu qaytarib bo'lmaydigan qaror
        # Shu sababli `check --deploy` security.W005 va W021 ogohlantirishlarini
        # beradi. Ular ataylab qoldirilgan, yashirilmagan.
        SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
        SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
