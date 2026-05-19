"""Cloudflare Access JWT verification.

Cloudflare puts a signed JWT in `Cf-Access-Jwt-Assertion` on every request
that has passed Access authentication. We verify against the team JWKS.

If `CF_ACCESS_AUD` is empty (local dev), auth is bypassed and a fake user
is returned.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import settings


_CACHE_TTL = 3600


@lru_cache(maxsize=1)
def _jwks_cache() -> dict[str, Any]:
    return {"fetched_at": 0.0, "keys": {}}


def _get_signing_key(kid: str) -> Any:
    cache = _jwks_cache()
    if time.time() - cache["fetched_at"] > _CACHE_TTL or kid not in cache["keys"]:
        url = f"https://{settings.cf_access_team_domain}/cdn-cgi/access/certs"
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        jwks = resp.json()
        cache["keys"] = {}
        for key in jwks.get("keys", []):
            cache["keys"][key["kid"]] = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        cache["fetched_at"] = time.time()
    if kid not in cache["keys"]:
        raise HTTPException(status_code=401, detail="Unknown signing key")
    return cache["keys"][kid]


class CurrentUser:
    def __init__(self, email: str, sub: str):
        self.email = email
        self.sub = sub


def get_current_user(
    cf_jwt: str | None = Header(default=None, alias="Cf-Access-Jwt-Assertion"),
) -> CurrentUser:
    if not settings.cf_access_aud:
        return CurrentUser(email="dev@local", sub="dev")

    if not cf_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Cloudflare Access JWT",
        )
    try:
        header = jwt.get_unverified_header(cf_jwt)
        key = _get_signing_key(header["kid"])
        payload = jwt.decode(
            cf_jwt,
            key=key,
            algorithms=["RS256"],
            audience=settings.cf_access_aud,
            issuer=f"https://{settings.cf_access_team_domain}",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {exc}") from exc

    email = payload.get("email") or payload.get("identity_nonce") or "unknown"
    return CurrentUser(email=email, sub=payload.get("sub", ""))


RequireUser = Depends(get_current_user)
