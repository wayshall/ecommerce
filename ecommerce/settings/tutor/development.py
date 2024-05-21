from ..devstack import *

import json
import os

SECRET_KEY = "wLwNaQASDJVTl0oZ91zc"
ALLOWED_HOSTS = [
    "ecommerce.local.edly.io",
    "ecommerce",
    "localhost"
]
PLATFORM_NAME = "My Open edX"
PROTOCOL = "http"

CORS_ALLOW_CREDENTIALS = True

OSCAR_DEFAULT_CURRENCY = "USD"

EDX_API_KEY = "Yh8PVlWXxc9CDdIbVRip"

JWT_AUTH["JWT_ISSUER"] = "http://local.edly.io/oauth2"
JWT_AUTH["JWT_AUDIENCE"] = "openedx"
JWT_AUTH["JWT_SECRET_KEY"] = "pEZUAIQHO7KJjaly1PQ0Item"
JWT_AUTH["JWT_PUBLIC_SIGNING_JWK_SET"] = json.dumps(
    {
        "keys": [
            {
                "kid": "openedx",
                "kty": "RSA",
                "e": "AQAB",
                "n": "tViKzMAFq1aY7TkDYvZlBE9A52MuI-8MDmlH4WQqRheL0ZDb2eqQtu3okyKelcS9Urk3A4xmoSS25J240p_58RZ64uqVhYmjzmMddVNBFZOK1zWEAXPy41OgAhkdekhyfpCKnxCal7nl546xOfILJWnO_XZ3dLBkMX5TbJ9gKKoNBkPxLJIAfSbt_pjTiwMBtft162DqNlj08XDkGXjsKXofQeag0Zxn76aXTmqBBbWgEvm8zyn0SpQWnOD8w2GYjhKYqm_D37isXI4wiLmxFe5nKInwOvdljI0kjpVuHDcUmyKJ-e23cPAOsEiWPhGBNSPFqarEhbG0ZldyHA-NrQ",
            }
        ]
    }
)
JWT_AUTH["JWT_ISSUERS"] = [
    {
        "ISSUER": "http://local.edly.io/oauth2",
        "AUDIENCE": "openedx",
        "SECRET_KEY": "pEZUAIQHO7KJjaly1PQ0Item"
    }
]

SOCIAL_AUTH_REDIRECT_IS_HTTPS = False
SOCIAL_AUTH_EDX_OAUTH2_ISSUER = "http://local.edly.io"
SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT = "http://lms:8000"

BACKEND_SERVICE_EDX_OAUTH2_SECRET = "V3OE4jg8"
BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL = "http://lms:8000/oauth2"

EDX_DRF_EXTENSIONS = {
    'OAUTH2_USER_INFO_URL': 'http://local.edly.io/oauth2/user_info',
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "ecommerce",
        "USER": "ecommerce",
        "PASSWORD": "ecommerce",
        "HOST": "openedxdb",
        "PORT": "3306",
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp"
EMAIL_PORT = "8025"
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = False

ENTERPRISE_SERVICE_URL = 'http://local.edly.io/enterprise/'
ENTERPRISE_API_URL = urljoin(ENTERPRISE_SERVICE_URL, 'api/v1/')

# Get rid of local logger
LOGGING["handlers"].pop("local")
for logger in LOGGING["loggers"].values():
    logger["handlers"].remove("local")

# Load payment processors
with open(
    os.path.join(os.path.dirname(__file__), "paymentprocessors.json"),
    encoding="utf8"
) as payment_processors_file:
    common_payment_processor_config = json.load(payment_processors_file)

# Fix cybersource-rest configuration
if "cybersource" in common_payment_processor_config and "cybersource-rest" not in common_payment_processor_config:
    common_payment_processor_config["cybersource-rest"] = common_payment_processor_config["cybersource"]
PAYMENT_PROCESSOR_CONFIG = {
    "openedx": common_payment_processor_config,
    "dev": common_payment_processor_config,
}
# Dummy config is required to bypass a KeyError
PAYMENT_PROCESSOR_CONFIG["edx"] = {
    "stripe": {
        "secret_key": "",
        "webhook_endpoint_secret": "",
    }
}
PAYMENT_PROCESSORS = list(PAYMENT_PROCESSORS) + []





CORS_ORIGIN_WHITELIST = list(CORS_ORIGIN_WHITELIST)






















CORS_ORIGIN_WHITELIST.append("http://apps.local.edly.io:7296")
CSRF_TRUSTED_ORIGINS = ["apps.local.edly.io:7296"]



CORS_ORIGIN_WHITELIST.append("http://apps.local.edly.io:1998")



SOCIAL_AUTH_EDX_OAUTH2_PUBLIC_URL_ROOT = "http://local.edly.io:8000"

BACKEND_SERVICE_EDX_OAUTH2_KEY = "ecommerce-dev"

