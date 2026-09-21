"""HTTP routes for accounts, TOTP, OAuth, and history."""

from __future__ import annotations

import io
import os
import secrets
import base64
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import pyotp
import qrcode
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.auth.store import (
    AuthStore,
    PENDING_2FA_COOKIE,
    SESSION_COOKIE,
    SESSION_DAYS,
    PENDING_2FA_SECONDS,
    current_user,
    is_proton_email,
)

OAUTH_PROVIDERS = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "userinfo": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
        "id_env": "GOOGLE_CLIENT_ID",
        "secret_env": "GOOGLE_CLIENT_SECRET",
    },
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "userinfo": "https://api.github.com/user",
        "scope": "read:user user:email",
        "id_env": "GITHUB_CLIENT_ID",
        "secret_env": "GITHUB_CLIENT_SECRET",
    },
    "proton": {
        "authorize": os.getenv("PROTON_AUTHORIZE_URL", "https://account.proton.me/oauth/authorize"),
        "token": os.getenv("PROTON_TOKEN_URL", "https://account.proton.me/api/io.proton.oauth/v1/token"),
        "userinfo": os.getenv("PROTON_USERINFO_URL", "https://account.proton.me/api/core/v4/users"),
        "scope": os.getenv("PROTON_OAUTH_SCOPE", "openid email"),
        "id_env": "PROTON_CLIENT_ID",
        "secret_env": "PROTON_CLIENT_SECRET",
    },
}


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TotpCodeRequest(BaseModel):
    code: str


class DisableTotpRequest(BaseModel):
    password: str
    code: str


def _signer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="retroark-auth")


def _cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _set_session_cookie(response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=SESSION_DAYS * 86400,
        path="/",
    )


def _clear_cookie(response, name: str) -> None:
    response.delete_cookie(name, path="/")


def _provider_configured(name: str) -> bool:
    spec = OAUTH_PROVIDERS[name]
    return bool(os.getenv(spec["id_env"]) and os.getenv(spec["secret_env"]))


def _public_base(request: Request) -> str:
    return (os.getenv("AUTH_PUBLIC_URL") or str(request.base_url)).rstrip("/")


def _totp_qr_data_uri(otpauth_url: str) -> str:
    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def build_auth_router(store: AuthStore, secret: str) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    signer = _signer(secret)

    def require_user(request: Request) -> Dict[str, Any]:
        user = current_user(request, store)
        if not user:
            raise HTTPException(status_code=401, detail="Sign in required.")
        return user

    @router.get("/providers")
    def auth_providers():
        return {
            "google": _provider_configured("google"),
            "github": _provider_configured("github"),
            "proton": _provider_configured("proton"),
        }

    @router.get("/me")
    def me(request: Request):
        user = current_user(request, store)
        if not user:
            return {"authenticated": False, "user": None}
        return {"authenticated": True, "user": store.public_user(user)}

    @router.post("/register")
    def register(req: RegisterRequest):
        try:
            user = store.create_user(req.email, req.password, req.display_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sid = store.create_session(user["id"])
        resp = JSONResponse({"status": "ok", "user": store.public_user(user)})
        _set_session_cookie(resp, sid)
        return resp

    @router.post("/login")
    def login(req: LoginRequest):
        user = store.authenticate(req.email, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        if user.get("totp_enabled"):
            token = signer.dumps({"uid": user["id"]})
            resp = JSONResponse({"status": "needs_2fa"})
            resp.set_cookie(
                PENDING_2FA_COOKIE,
                token,
                httponly=True,
                samesite="lax",
                secure=_cookie_secure(),
                max_age=PENDING_2FA_SECONDS,
                path="/",
            )
            return resp
        sid = store.create_session(user["id"])
        resp = JSONResponse({"status": "ok", "user": store.public_user(user)})
        _set_session_cookie(resp, sid)
        return resp

    @router.post("/login/2fa")
    def login_2fa(req: TotpCodeRequest, request: Request):
        pending = request.cookies.get(PENDING_2FA_COOKIE)
        if not pending:
            raise HTTPException(status_code=401, detail="Password login required first.")
        try:
            data = signer.loads(pending, max_age=PENDING_2FA_SECONDS)
        except (BadSignature, SignatureExpired) as exc:
            raise HTTPException(status_code=401, detail="Two-factor challenge expired.") from exc
        user = store.get_user(data["uid"])
        if not user or not user.get("totp_secret"):
            raise HTTPException(status_code=401, detail="Two-factor is not configured.")
        if not pyotp.TOTP(user["totp_secret"]).verify(req.code.strip(), valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid authenticator code.")
        sid = store.create_session(user["id"])
        resp = JSONResponse({"status": "ok", "user": store.public_user(user)})
        _set_session_cookie(resp, sid)
        _clear_cookie(resp, PENDING_2FA_COOKIE)
        return resp

    @router.post("/logout")
    def logout(request: Request):
        store.delete_session(request.cookies.get(SESSION_COOKIE))
        resp = JSONResponse({"status": "ok"})
        _clear_cookie(resp, SESSION_COOKIE)
        _clear_cookie(resp, PENDING_2FA_COOKIE)
        return resp

    @router.post("/2fa/setup")
    def totp_setup(request: Request):
        user = require_user(request)
        secret = pyotp.random_base32()
        store.set_totp_secret(user["id"], secret)
        uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="RetroArk")
        return {"secret": secret, "otpauth_url": uri, "qr_data_uri": _totp_qr_data_uri(uri)}

    @router.post("/2fa/enable")
    def totp_enable(req: TotpCodeRequest, request: Request):
        user = require_user(request)
        if not user.get("totp_secret"):
            raise HTTPException(status_code=400, detail="Call /api/auth/2fa/setup first.")
        if not pyotp.TOTP(user["totp_secret"]).verify(req.code.strip(), valid_window=1):
            raise HTTPException(status_code=400, detail="Invalid authenticator code.")
        store.enable_totp(user["id"])
        return {"status": "ok", "totp_enabled": True}

    @router.post("/2fa/disable")
    def totp_disable(req: DisableTotpRequest, request: Request):
        user = require_user(request)
        if not user.get("password_hash") or not store.authenticate(user["email"], req.password):
            raise HTTPException(status_code=401, detail="Password is required to disable 2FA.")
        if user.get("totp_enabled") and user.get("totp_secret"):
            if not pyotp.TOTP(user["totp_secret"]).verify(req.code.strip(), valid_window=1):
                raise HTTPException(status_code=401, detail="Invalid authenticator code.")
        store.disable_totp(user["id"])
        return {"status": "ok", "totp_enabled": False}

    @router.get("/oauth/{provider}/start")
    def oauth_start(provider: str, request: Request):
        provider = provider.lower()
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(status_code=404, detail="Unknown provider.")
        if not _provider_configured(provider):
            raise HTTPException(
                status_code=400,
                detail=f"{provider} login is not configured. Set {OAUTH_PROVIDERS[provider]['id_env']} and {OAUTH_PROVIDERS[provider]['secret_env']}.",
            )
        spec = OAUTH_PROVIDERS[provider]
        state = secrets.token_urlsafe(24)
        redirect_uri = f"{_public_base(request)}/api/auth/oauth/{provider}/callback"
        params = {
            "client_id": os.getenv(spec["id_env"]),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": spec["scope"],
            "state": state,
        }
        if provider == "google":
            params["access_type"] = "online"
            params["include_granted_scopes"] = "true"
        url = spec["authorize"] + "?" + urlencode(params)
        resp = RedirectResponse(url, status_code=302)
        resp.set_cookie(
            "retroark_oauth_state",
            signer.dumps({"state": state, "provider": provider}),
            httponly=True,
            samesite="lax",
            secure=_cookie_secure(),
            max_age=600,
            path="/",
        )
        return resp

    @router.get("/oauth/{provider}/callback")
    def oauth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None):
        provider = provider.lower()
        if provider not in OAUTH_PROVIDERS:
            raise HTTPException(status_code=404, detail="Unknown provider.")
        if not code:
            raise HTTPException(status_code=400, detail="Missing OAuth code.")
        raw_state = request.cookies.get("retroark_oauth_state")
        try:
            saved = signer.loads(raw_state or "", max_age=600)
        except (BadSignature, SignatureExpired) as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc
        if saved.get("state") != state or saved.get("provider") != provider:
            raise HTTPException(status_code=400, detail="OAuth state mismatch.")
        spec = OAUTH_PROVIDERS[provider]
        redirect_uri = f"{_public_base(request)}/api/auth/oauth/{provider}/callback"
        token_resp = requests.post(
            spec["token"],
            data={
                "client_id": os.getenv(spec["id_env"]),
                "client_secret": os.getenv(spec["secret_env"]),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        if not token_resp.ok:
            raise HTTPException(status_code=401, detail=f"{provider} token exchange failed.")
        token_data = token_resp.json()
        access = token_data.get("access_token")
        if not access:
            raise HTTPException(status_code=401, detail=f"{provider} did not return an access token.")
        info_resp = requests.get(
            spec["userinfo"],
            headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
            timeout=20,
        )
        if not info_resp.ok:
            raise HTTPException(status_code=401, detail=f"{provider} user info failed.")
        info = info_resp.json()
        if provider == "github" and not info.get("email"):
            mail_resp = requests.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
                timeout=20,
            )
            if mail_resp.ok:
                emails = mail_resp.json()
                primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
                info["email"] = (primary or (emails[0] if emails else {})).get("email")
        if provider == "proton":
            # Proton user payloads nest the account under User / Emails.
            nested = info.get("User") or info
            info["id"] = nested.get("ID") or nested.get("id") or info.get("sub")
            emails = nested.get("Emails") or nested.get("emails") or []
            if isinstance(emails, list) and emails:
                first = emails[0]
                info["email"] = first.get("Email") if isinstance(first, dict) else str(first)
            info["email"] = info.get("email") or nested.get("Email") or nested.get("email")
            info["name"] = nested.get("Name") or nested.get("name") or info.get("name")
        provider_user_id = str(info.get("id") or info.get("sub") or "")
        email = (info.get("email") or "").strip().lower()
        name = info.get("name") or info.get("login") or (email.split("@")[0] if email else provider)
        if not provider_user_id:
            raise HTTPException(status_code=401, detail=f"{provider} did not return a user id.")
        if provider == "proton" and email and not is_proton_email(email):
            raise HTTPException(status_code=400, detail="Proton login must use a Proton Mail address.")
        user = store.find_oauth(provider, provider_user_id)
        if not user and email:
            user = store.get_user_by_email(email)
        if not user:
            if not email:
                email = f"{provider_user_id}@{provider}.oauth.local"
            try:
                user = store.create_user(email, password=None, display_name=name)
            except ValueError:
                user = store.get_user_by_email(email)
        store.link_oauth(user["id"], provider, provider_user_id, email or None)
        sid = store.create_session(user["id"])
        dest = f"{_public_base(request)}/app?auth=ok"
        resp = RedirectResponse(dest, status_code=302)
        _set_session_cookie(resp, sid)
        _clear_cookie(resp, "retroark_oauth_state")
        return resp

    @router.get("/history")
    def history(request: Request):
        user = require_user(request)
        return {"records": store.list_history(user["id"])}

    return router


def persist_generation(store: AuthStore, user_id: Optional[str], record: Dict[str, Any]) -> None:
    if not user_id:
        return
    store.add_history(user_id, record)
