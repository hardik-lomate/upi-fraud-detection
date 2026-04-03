"""
API Authentication — JWT-based API key authentication.
Each client/partner gets an API key. All requests must include it.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import hashlib
import os

# In production, load from environment variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "upi-fraud-detection-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Simple API key store (in production, use a database)
API_KEYS = {
    "demo-api-key-001": {
        "client_name": "Demo Client",
        "permissions": ["predict", "transactions", "audit"],
        "rate_limit": 100,  # requests per minute
        "active": True,
    },
    "test-api-key-002": {
        "client_name": "Test Client",
        "permissions": ["predict", "transactions"],
        "rate_limit": 50,
        "active": True,
    },
}


security = HTTPBearer(auto_error=False)


def create_access_token(api_key: str) -> str:
    """Generate a JWT token for an API key."""
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
    """Decode and validate a JWT token."""
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
    """
    FastAPI dependency for authenticated endpoints.
    Supports both JWT Bearer tokens and direct API keys.
    """
    if credentials is None:
        # Allow unauthenticated access in development mode
        if os.getenv("AUTH_REQUIRED", "false").lower() == "true":
            raise HTTPException(status_code=401, detail="Authentication required. Provide Bearer token.")
        return {"sub": "anonymous", "client": "Anonymous", "permissions": ["predict", "transactions"]}

    token = credentials.credentials

    # Check if it's a direct API key
    if token in API_KEYS:
        client = API_KEYS[token]
        if not client["active"]:
            raise HTTPException(status_code=403, detail="API key deactivated")
        return {"sub": token, "client": client["client_name"], "permissions": client["permissions"]}

    # Otherwise, treat as JWT
    return verify_token(token)


def check_permission(client: dict, required_permission: str):
    """Verify the client has the required permission."""
    if required_permission not in client.get("permissions", []):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied. Required: {required_permission}",
        )
