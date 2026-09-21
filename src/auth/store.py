"""SQLite-backed users, sessions, OAuth identities, and generation history."""

from __future__ import annotations

import os
import secrets
import sqlite3
import uuid
import time
from typing import Any, Dict, List, Optional

import bcrypt

SESSION_COOKIE = "retroark_session"
PENDING_2FA_COOKIE = "retroark_2fa_pending"
SESSION_DAYS = 30
PENDING_2FA_SECONDS = 600

PROTON_EMAIL_DOMAINS = ("proton.me", "protonmail.com", "protonmail.ch", "pm.me")


def session_cookie_name() -> str:
    return SESSION_COOKIE


def load_or_create_secret(data_dir: str) -> str:
    env = os.getenv("AUTH_SECRET")
    if env and env.strip():
        return env.strip()
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, ".auth_secret")
    if os.path.exists(path):
        return open(path, "r", encoding="utf-8").read().strip()
    secret = secrets.token_urlsafe(48)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(secret)
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def is_proton_email(email: str) -> bool:
    host = (email or "").rsplit("@", 1)[-1].lower()
    return host in PROTON_EMAIL_DOMAINS


class AuthStore:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "accounts.db")
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT,
                    display_name TEXT,
                    totp_secret TEXT,
                    totp_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_identities (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_user_id TEXT NOT NULL,
                    email TEXT,
                    UNIQUE(provider, provider_user_id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS generation_history (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    prompt TEXT,
                    model TEXT,
                    mode TEXT,
                    media_type TEXT,
                    path TEXT,
                    elapsed_seconds INTEGER,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )

    def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        email = email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("A valid email is required.")
        if password is not None and len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        user_id = str(uuid.uuid4())
        pw_hash = hash_password(password) if password else None
        name = (display_name or email.split("@")[0]).strip()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, email, pw_hash, name, time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with that email already exists.") from exc
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        return dict(row) if row else None

    def public_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name") or user["email"].split("@")[0],
            "totp_enabled": bool(user.get("totp_enabled")),
            "has_password": bool(user.get("password_hash")),
        }

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_email(email)
        if not user or not user.get("password_hash"):
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    def create_session(self, user_id: str) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (sid, user_id, now, now + SESSION_DAYS * 86400),
            )
        return sid

    def get_session_user(self, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not row or row["expires_at"] < time.time():
                if row:
                    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                return None
        return self.get_user(row["user_id"])

    def delete_session(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def set_totp_secret(self, user_id: str, secret: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET totp_secret = ?, totp_enabled = 0 WHERE id = ?",
                (secret, user_id),
            )

    def enable_totp(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET totp_enabled = 1 WHERE id = ?", (user_id,))

    def disable_totp(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET totp_secret = NULL, totp_enabled = 0 WHERE id = ?",
                (user_id,),
            )

    def link_oauth(self, user_id: str, provider: str, provider_user_id: str, email: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO oauth_identities (id, user_id, provider, provider_user_id, email)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(provider, provider_user_id) DO UPDATE SET
                     user_id = excluded.user_id,
                     email = excluded.email""",
                (str(uuid.uuid4()), user_id, provider, provider_user_id, email),
            )

    def find_oauth(self, provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM oauth_identities WHERE provider = ? AND provider_user_id = ?",
                (provider, provider_user_id),
            ).fetchone()
        return self.get_user(row["user_id"]) if row else None

    def add_history(self, user_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        hid = record.get("id") or str(uuid.uuid4())
        row = {
            "id": hid,
            "user_id": user_id,
            "title": (record.get("title") or record.get("prompt") or "Generation")[:80],
            "prompt": record.get("prompt") or "",
            "model": record.get("model") or "",
            "mode": record.get("mode") or "",
            "media_type": record.get("media_type") or "image",
            "path": record.get("path") or "",
            "elapsed_seconds": int(record.get("elapsed_seconds") or 0),
            "created_at": time.time(),
        }
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO generation_history
                   (id, user_id, title, prompt, model, mode, media_type, path, elapsed_seconds, created_at)
                   VALUES (:id, :user_id, :title, :prompt, :model, :mode, :media_type, :path, :elapsed_seconds, :created_at)""",
                row,
            )
        return row

    def list_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM generation_history WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def current_user(request, store: AuthStore) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    return store.get_session_user(token)
