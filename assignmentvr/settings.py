from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv() 

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-s2$nh-+all6oc5sgd59b&r@_c=_383wy3#7#wngfl1-tiw+@@l'

DEBUG = True

ALLOWED_HOSTS = [    
                 'assignment-2sc3.onrender.com',
                 'localhost',
                 '127.0.0.1',
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'products',
    'design_agent',
    'showroom_agent',
    'corsheaders'
    
]

MIDDLEWARE = [
    
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'assignmentvr.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'assignmentvr.wsgi.application'


OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'assignment',            # your database name
#         'USER': 'root',          # your database user (or 'root')
#         'PASSWORD': 'om@123',     # your password
#         'HOST': 'localhost',               # or '127.0.0.1'
#         'PORT': '5432',                    # default MySQL port
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'assignment_fvgi',
        'USER': 'assignment_fvgi_user',
        'PASSWORD': 'vjFLc4VVC7Fo92wcZIM1u887LPcugCzJ',
        'HOST': 'dpg-d18vm6vfte5s73brdrvg-a',
        'PORT': '5432',
    }
}


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'postgres',  # Default database name
#         'USER': 'postgres',
#         'PASSWORD': 'postgres#1234',
#         'HOST': 'django-db.c7wakw400mh1.eu-north-1.rds.amazonaws.com',  # You'll get this after creation
#         'PORT': '5432',
#     }
# }

# DATABASES = {
#     'default': dj_database_url.config(default=os.getenv('DATABASE_URL'))
# }


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}


STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
