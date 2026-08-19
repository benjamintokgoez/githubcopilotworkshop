"""qxm.auth — Authentication, request signing, and API key management.

No secret material is defined in this package: the key manager secret is
supplied explicitly or via the ``QXM_AUTH_SECRET_KEY`` environment variable.
"""

from qxm.auth.keys import (
    DEFAULT_PERMISSIONS,
    KEY_PREFIX,
    SECRET_ENV_NAME,
    VALID_PERMISSIONS,
    APIKey,
    KeyManager,
)
from qxm.auth.signing import (
    DEFAULT_MAX_AGE_SECONDS,
    canonical_request,
    sign_request,
    verify_signature,
)

__all__ = [
    "APIKey",
    "KeyManager",
    "SECRET_ENV_NAME",
    "KEY_PREFIX",
    "VALID_PERMISSIONS",
    "DEFAULT_PERMISSIONS",
    "DEFAULT_MAX_AGE_SECONDS",
    "canonical_request",
    "sign_request",
    "verify_signature",
]
