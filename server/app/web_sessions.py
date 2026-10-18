"""Password verification and revocable database sessions for the reporting UI."""

import asyncio
import hashlib
import hmac
import secrets

from . import db
from .config import settings

SESSION_SECONDS = 8 * 60 * 60
ITERATIONS = 600_000


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, _ = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        return hmac.compare_digest(password_hash(password, salt), stored)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Unknown users still perform a password derivation before returning the same error.
DUMMY_PASSWORD_HASH = password_hash(secrets.token_urlsafe(32))


async def ensure_demo_account():
    """Provision only on first startup; restarts never overwrite stored credentials."""
    existing = await db.run(
        "SELECT 1 FROM reporting.web_account WHERE username=%s",
        (settings.login_username,),
        pool=db.admin_pool,
        one=True,
    )
    if existing:
        return
    hashed = await asyncio.to_thread(password_hash, settings.login_password)
    await db.run(
        """INSERT INTO reporting.web_account(username,password_hash) VALUES (%s,%s)
        ON CONFLICT(username) DO NOTHING""",
        (settings.login_username, hashed),
        pool=db.admin_pool,
    )


async def create_session(username: str, password: str) -> str | None:
    account = await db.run(
        "SELECT * FROM reporting.web_account WHERE username=%s",
        (username,),
        pool=db.admin_pool,
        one=True,
    )
    valid = await asyncio.to_thread(
        password_matches,
        password,
        account["password_hash"] if account else DUMMY_PASSWORD_HASH,
    )
    if not valid or not account or not account["enabled"]:
        return None
    token = "ws_" + secrets.token_urlsafe(32)
    await db.run(
        "DELETE FROM reporting.web_session WHERE expires_at<=now()", pool=db.admin_pool
    )
    await db.run(
        "INSERT INTO reporting.web_session(token_hash,account_id) VALUES (%s,%s)",
        (token_hash(token), account["account_id"]),
        pool=db.admin_pool,
    )
    return token


async def session_account(token: str):
    return await db.run(
        """SELECT a.account_id,a.username FROM reporting.web_session s
        JOIN reporting.web_account a USING(account_id)
        WHERE s.token_hash=%s AND s.expires_at>now() AND a.enabled""",
        (token_hash(token),),
        pool=db.admin_pool,
        one=True,
    )


async def revoke_session(token: str | None):
    if token and token.startswith("ws_"):
        await db.run(
            "DELETE FROM reporting.web_session WHERE token_hash=%s",
            (token_hash(token),),
            pool=db.admin_pool,
        )
