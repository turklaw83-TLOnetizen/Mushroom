# ---- Authentication & Authorization ---------------------------------------
# Clerk SDK integration for session verification + RBAC.
#
# Production: Verifies Clerk JWTs via JWKS (RS256 signature verification).
# Development: Supports legacy PIN-based auth via JWT (HS256).

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# ---- Configuration -------------------------------------------------------
# Read env vars LAZILY (not at import time) so .env loading order doesn't matter.

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Cache for Clerk JWKS public key
_clerk_jwks_client = None


def _get_clerk_secret_key() -> str:
    return os.getenv("CLERK_SECRET_KEY", "")


def _get_clerk_jwks_url() -> str:
    return os.getenv("CLERK_JWKS_URL", "")


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-secret-change-in-production")


# ---- Clerk JWKS Verification (Fix #7) -----------------------------------

def _get_clerk_jwks_client():
    """Lazily initialize and cache the Clerk JWKS client."""
    global _clerk_jwks_client
    if _clerk_jwks_client is not None:
        return _clerk_jwks_client

    if not _get_clerk_jwks_url() and not _get_clerk_secret_key():
        return None

    try:
        import jwt as pyjwt

        # Auto-discover JWKS URL from Clerk secret key if not set
        jwks_url = _get_clerk_jwks_url()
        if not jwks_url and _get_clerk_secret_key():
            # Clerk secret keys start with "sk_test_" or "sk_live_"
            # The JWKS URL follows the pattern for the Clerk instance
            # User should set CLERK_JWKS_URL explicitly in .env
            logger.warning(
                "CLERK_JWKS_URL not set. Set it to "
                "https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json"
            )
            return None

        _clerk_jwks_client = pyjwt.PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=3600,  # Cache JWKS for 1 hour
        )
        logger.info("Clerk JWKS client initialized: %s", jwks_url)
        return _clerk_jwks_client
    except ImportError:
        logger.warning("PyJWT not installed; Clerk auth disabled")
        return None
    except Exception as e:
        logger.error("Failed to initialize Clerk JWKS client: %s", e)
        return None


async def _verify_clerk_session(token: str) -> Optional[dict]:
    """
    Verify a Clerk session token using JWKS (RS256).

    Downloads the public key from Clerk's JWKS endpoint,
    verifies the JWT signature, and returns claims.
    """
    if not _get_clerk_secret_key():
        return None

    try:
        import jwt as pyjwt

        jwks_client = _get_clerk_jwks_client()
        if jwks_client is None:
            # Fallback: decode without signature verification (dev only)
            logger.warning("JWKS not configured — decoding Clerk JWT WITHOUT signature verification")
            claims = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            return claims

        # Production: verify signature via JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Clerk doesn't set audience by default
                "verify_iss": True,
            },
        )
        return claims
    except ImportError:
        logger.warning("PyJWT not installed; Clerk auth disabled")
        return None
    except Exception as e:
        logger.debug("Clerk token verification failed: %s", e)
        return None


# ---- Legacy JWT Auth (development/fallback) ------------------------------

def _create_jwt(user_id: str, role: str = "attorney", name: str = "") -> str:
    """Create a simple JWT for development/PIN-based auth."""
    import jwt as pyjwt

    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return pyjwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _verify_jwt(token: str) -> Optional[dict]:
    """Verify a legacy JWT. Returns claims or None."""
    try:
        import jwt as pyjwt

        return pyjwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


def hash_pin(pin: str) -> str:
    """One-way SHA-256 hash of a PIN (matches core/user_profiles.py)."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


# ---- FastAPI Dependency --------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Authenticate the request and return the current user dict.

    Tries Clerk first (JWKS-verified RS256), then falls back to legacy JWT.
    Returns a dict with at minimum: {id, role, name}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Try Clerk first
    if _get_clerk_secret_key():
        claims = await _verify_clerk_session(token)
        if claims:
            return {
                "id": claims.get("sub", ""),
                "clerk_id": claims.get("sub", ""),
                "role": claims.get("role", claims.get("public_metadata", {}).get("role", "attorney")),
                "name": claims.get("name", ""),
                "email": claims.get("email", ""),
            }

    # Fall back to legacy JWT
    claims = _verify_jwt(token)
    if claims:
        return {
            "id": claims.get("sub", ""),
            "role": claims.get("role", "attorney"),
            "name": claims.get("name", ""),
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---- Role-Based Access Control ------------------------------------------

def require_role(*allowed_roles: str):
    """
    Dependency factory that enforces role-based access.

    Usage:
        @router.get("/admin-only")
        def admin_endpoint(user = Depends(require_role("admin"))):
            ...
    """
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(allowed_roles)}",
            )
        return user
    return checker
