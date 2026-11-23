from fastapi import HTTPException, Request

from backend.auth import hash_session_token
from database.auth_storage import get_session_user

COOKIE_NAME = "incidentgraph_session"


def get_current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    user = get_session_user(hash_session_token(token))

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid.",
        )

    return user


def require_active_user(request: Request):
    user = get_current_user(request)

    if not user["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled.",
        )

    return user


def require_admin(request: Request):
    user = require_active_user(request)

    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

    return user
