import os
import re
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.auth import (
    hash_password,
    verify_password,
    create_session_token,
    hash_session_token,
)
from database.auth_storage import (
    create_user,
    get_user_by_email,
    create_session,
    get_session_user,
    delete_session,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_NAME = "incidentgraph_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
SESSION_DURATION_HOURS = 24


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def validate_email(email):
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
        email,
    ):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def set_session_cookie(response, token):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_DURATION_HOURS * 3600,
        path="/",
    )


@router.post("/register", status_code=201)
def register(data: RegisterRequest, response: Response):
    email = validate_email(data.email)

    try:
        password_hash = hash_password(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        user_id = create_user(email, password_hash, role="user")
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    token = create_session_token()
    create_session(user_id, hash_session_token(token), SESSION_DURATION_HOURS)
    set_session_cookie(response, token)

    return {
        "message": "Account created successfully.",
        "user": {
            "id": user_id,
            "email": email,
            "role": "user",
        },
    }


@router.post("/login")
def login(data: LoginRequest, response: Response):
    email = validate_email(data.email)
    user = get_user_by_email(email)

    if (
        not user
        or not user["is_active"]
        or not verify_password(data.password, user["password_hash"])
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    token = create_session_token()
    create_session(user["id"], hash_session_token(token), SESSION_DURATION_HOURS)
    set_session_cookie(response, token)

    return {
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
        },
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)

    if token:
        delete_session(hash_session_token(token))

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )

    return {"message": "Logged out successfully."}


@router.get("/me")
def current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    user = get_session_user(hash_session_token(token))

    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    return {"user": user}
