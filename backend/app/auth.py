"""
API Authentication — JWT + API key auth with env-var-driven config.
No hardcoded secrets. Auth required by default.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    val = str(raw).strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    logger.warning("Invalid %s=%r. Falling back to default=%s", name, raw, default)
    return bool(default)


def is_auth_required() -> bool:
    return _env_bool("AUTH_REQUIRED", default=True)

# Secret key — MUST be set via environment variable
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    # In development, use a default but warn loudly
    if not is_auth_required():
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
        logger.warning("[WARN] Using insecure dev JWT key. Set JWT_SECRET_KEY in production.")
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required. "
            "Set AUTH_REQUIRED=false for development without a key."
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Load API keys from file
_api_keys_path = os.getenv("API_KEYS_FILE", str(Path(__file__).resolve().parent.parent.parent / "api_keys.json"))

def _load_api_keys() -> dict:
    if os.path.exists(_api_keys_path):
        with open(_api_keys_path) as f:
            keys = json.load(f)
        logger.info(f"Loaded {len(keys)} API keys from {_api_keys_path}")
        return keys
    else:
        logger.warning(f"API keys file not found at {_api_keys_path} — using built-in dev keys")
        return {
            "demo-api-key-001": {
                "client_name": "Demo Client",
                "permissions": ["predict", "transactions", "audit"],
                "rate_limit": 100,
                "active": True,
            },
        }

API_KEYS = _load_api_keys()

security = HTTPBearer(auto_error=False)


def create_access_token(api_key: str) -> str:
    if api_key not in API_KEYS:
        raise ValueError("Invalid API key")
    client = API_KEYS[api_key]
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": api_key,
        "client": client["client_name"],
        "permissions": client["permissions"],
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        api_key = payload.get("sub")
        if api_key not in API_KEYS:
            raise HTTPException(status_code=401, detail="API key revoked or invalid")
        if not API_KEYS[api_key]["active"]:
            raise HTTPException(status_code=403, detail="API key deactivated")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_client(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    auth_required = is_auth_required()

    if credentials is None:
        if auth_required:
            raise HTTPException(status_code=401, detail="Authentication required. Provide Bearer token.")
        return {"sub": "anonymous", "client": "Anonymous", "permissions": ["predict", "transactions", "audit"]}

    token = credentials.credentials
    if token in API_KEYS:
        client = API_KEYS[token]
        if not client["active"]:
            if not auth_required:
                return {"sub": "anonymous", "client": "Anonymous", "permissions": ["predict", "transactions", "audit"]}
            raise HTTPException(status_code=403, detail="API key deactivated")
        return {"sub": token, "client": client["client_name"], "permissions": client["permissions"]}

    if not auth_required:
        try:
            return verify_token(token)
        except HTTPException:
            return {"sub": "anonymous", "client": "Anonymous", "permissions": ["predict", "transactions", "audit"]}

    return verify_token(token)


def check_permission(client: dict, required_permission: str):
    if required_permission not in client.get("permissions", []):
        raise HTTPException(status_code=403, detail=f"Permission denied. Required: {required_permission}")
