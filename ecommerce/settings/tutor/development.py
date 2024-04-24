from ..devstack import *

import json
import os

SECRET_KEY = "Ai8OzavSEhVFp1BHaZNG"
ALLOWED_HOSTS = [
    "ecommerce.local.edly.io",
    "ecommerce",
]
PLATFORM_NAME = "my openedx"
PROTOCOL = "http"

CORS_ALLOW_CREDENTIALS = True

OSCAR_DEFAULT_CURRENCY = "USD"

EDX_API_KEY = "VQdvs9R4gr68CTVQuFyQ"

JWT_AUTH["JWT_ISSUER"] = "http://local.edly.io/oauth2"
JWT_AUTH["JWT_AUDIENCE"] = "openedx"
JWT_AUTH["JWT_SECRET_KEY"] = "GjfJ8bSEGNWFLtXHF0Nd7Ezm"
JWT_AUTH["JWT_PUBLIC_SIGNING_JWK_SET"] = json.dumps(
    {
        "keys": [
            {
                "kid": "openedx",
                "kty": "RSA",
                "e": "AQAB",
                "n": "o4jum602akkN3ijjYz5L-Olt09SwU74AAHArntbI3ywzoK4oTRgcKmCt6iNusaCKw7PW-R5GX73UgQq1hZNoeuluV69SVeO6Y1GUrH4KYTqSuVsS1Y1WsLFvpGOwTbJSqE1q1R2J_Hhxf-8DX-UiP3x71ybx8jNXwI7kFc5Sa5V1XPQmqI0Vq6IrSvFYAkdRXB3YDmnvGM_RwgOjojNlNr-n81adma5UCEpfsaoubkfZw-wtXbM92wl1rmKeJb2Ax1W5v_7riwWr_ozOG8at3y9-BBHvVPl6Nb1vYppTo0V0JtQjEYe2H7Q577uYfsRpo0iRiaW05QlRMf06R8MI6w",
            }
        ]
    }
)
JWT_AUTH["JWT_ISSUERS"] = [
    {
        "ISSUER": "http://local.edly.io/oauth2",
        "AUDIENCE": "openedx",
        "SECRET_KEY": "GjfJ8bSEGNWFLtXHF0Nd7Ezm"
    }
]

SOCIAL_AUTH_REDIRECT_IS_HTTPS = False
SOCIAL_AUTH_EDX_OAUTH2_ISSUER = "http://local.edly.io"
SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT = "http://lms:8000"

BACKEND_SERVICE_EDX_OAUTH2_SECRET = "SXhYIdah"
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

