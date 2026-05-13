import os
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'audit': {
            'format': 'AUDIT {asctime} [{levelname}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file_general': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'django.log'),
            'formatter': 'verbose',
        },
        'file_audit': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'audit.log'),
            'formatter': 'audit',
        },
        'file_security': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'security.log'),
            'formatter': 'verbose',
        },
        'file_otp': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'otp.log'),
            'formatter': 'audit',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_general'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['file_security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'audit': {
            'handlers': ['file_audit', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'otp': {
            'handlers': ['file_otp', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'core.otp_service': {
            'handlers': ['file_otp', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'dashboard.views': {
            'handlers': ['file_audit', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
