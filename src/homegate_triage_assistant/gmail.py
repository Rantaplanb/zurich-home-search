from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import Config
from .ingest import parse_homegate_email
from .schemas import ParsedAlert


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass(slots=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float
    scope: str = GMAIL_SCOPE
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60

    def as_json(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "token_type": self.token_type,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "OAuthTokens":
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token"),
            expires_at=float(payload["expires_at"]),
            scope=str(payload.get("scope", GMAIL_SCOPE)),
            token_type=str(payload.get("token_type", "Bearer")),
        )


class GmailAuth:
    def __init__(self, config: Config) -> None:
        self.config = config

    def authenticate(self, timeout_seconds: int = 300) -> OAuthTokens:
        if not self.config.gmail.is_configured:
            raise RuntimeError("GOOGLE_CLIENT_ID is not configured.")

        redirect_uri = f"http://127.0.0.1:{self.config.gmail.auth_port}/oauth2callback"
        verifier = _random_verifier()
        challenge = _pkce_challenge(verifier)
        state = secrets.token_urlsafe(24)
        callback = _CallbackServer(self.config.gmail.auth_port, expected_state=state)
        callback.start()
        url = self._authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
        )
        print(f"Open this URL to authorize Gmail access:\n{url}\n")
        if self.config.gmail.open_browser:
            webbrowser.open(url, new=1, autoraise=True)

        code = callback.wait_for_code(timeout_seconds=timeout_seconds)
        tokens = self._exchange_code(
            code=code,
            verifier=verifier,
            redirect_uri=redirect_uri,
        )
        self.save_tokens(tokens)
        return tokens

    def load_tokens(self) -> OAuthTokens | None:
        token_path = self.config.gmail.token_path
        if not token_path.exists():
            return None
        return OAuthTokens.from_json(json.loads(token_path.read_text()))

    def save_tokens(self, tokens: OAuthTokens) -> None:
        self.config.gmail.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.gmail.token_path.write_text(json.dumps(tokens.as_json(), indent=2))

    def ensure_tokens(self) -> OAuthTokens:
        tokens = self.load_tokens()
        if tokens is None:
            raise RuntimeError("No Gmail token file found. Run `homegate-triage-assistant gmail-auth` first.")
        if not tokens.is_expired:
            return tokens
        if not tokens.refresh_token:
            raise RuntimeError("Gmail access token expired and no refresh token is available.")
        refreshed = self._refresh_tokens(tokens.refresh_token)
        self.save_tokens(refreshed)
        return refreshed

    def _authorization_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self.config.gmail.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _exchange_code(self, *, code: str, verifier: str, redirect_uri: str) -> OAuthTokens:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": self.config.gmail.client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return OAuthTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + float(payload["expires_in"]),
            scope=payload.get("scope", GMAIL_SCOPE),
            token_type=payload.get("token_type", "Bearer"),
        )

    def _refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": self.config.gmail.client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        return OAuthTokens(
            access_token=payload["access_token"],
            refresh_token=refresh_token,
            expires_at=time.time() + float(payload["expires_in"]),
            scope=payload.get("scope", GMAIL_SCOPE),
            token_type=payload.get("token_type", "Bearer"),
        )


class GmailAlertFetcher:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.auth = GmailAuth(config)

    def poll(self) -> list[ParsedAlert]:
        if not self.config.gmail.is_configured:
            return []
        tokens = self.auth.ensure_tokens()
        message_ids = self._list_message_ids(tokens)
        alerts: list[ParsedAlert] = []
        for message_id in message_ids:
            raw_message = self._fetch_raw_message(tokens, message_id)
            parsed = parse_homegate_email(raw_message, self.config)
            if parsed is not None:
                alerts.append(parsed)
        return alerts

    @staticmethod
    def build_listing_refs(alert: ParsedAlert) -> list[tuple[str, str, str | None]]:
        from .ingest import IMAPAlertFetcher

        return IMAPAlertFetcher.build_listing_refs(alert)

    def test_access(self) -> dict[str, Any]:
        tokens = self.auth.ensure_tokens()
        profile = self._api_get(tokens, "/profile")
        message_ids = self._list_message_ids(tokens)
        return {
            "emailAddress": profile.get("emailAddress"),
            "messagesMatched": len(message_ids),
            "query": self.config.gmail.query,
        }

    def _list_message_ids(self, tokens: OAuthTokens) -> list[str]:
        payload = self._api_get(
            tokens,
            "/messages",
            params={
                "q": self.config.gmail.query,
                "maxResults": str(self.config.gmail.max_results),
            },
        )
        return [message["id"] for message in payload.get("messages", [])]

    def _fetch_raw_message(self, tokens: OAuthTokens, message_id: str) -> bytes:
        payload = self._api_get(tokens, f"/messages/{message_id}", params={"format": "raw"})
        raw = payload["raw"]
        padding = "=" * (-len(raw) % 4)
        return base64.urlsafe_b64decode(raw + padding)

    def _api_get(self, tokens: OAuthTokens, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = httpx.get(
            f"{GMAIL_API_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {tokens.access_token}"},
            timeout=20.0,
        )
        response.raise_for_status()
        return response.json()


class _CallbackServer:
    def __init__(self, port: int, expected_state: str) -> None:
        self.port = port
        self.expected_state = expected_state
        self.code: str | None = None
        self.error: str | None = None
        self._event = threading.Event()

        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                state = params.get("state", [None])[0]
                if state != parent.expected_state:
                    parent.error = "OAuth state mismatch."
                else:
                    parent.code = params.get("code", [None])[0]
                    parent.error = params.get("error", [None])[0]

                body = (
                    "Gmail auth complete. You can return to Codex."
                    if parent.code and not parent.error
                    else f"Gmail auth failed: {parent.error or 'unknown error'}"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                parent._event.set()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        self._server = HTTPServer(("127.0.0.1", port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def wait_for_code(self, timeout_seconds: int) -> str:
        if not self._event.wait(timeout_seconds):
            self.close()
            raise RuntimeError("Timed out waiting for Gmail OAuth callback.")
        self.close()
        if self.error:
            raise RuntimeError(f"Gmail OAuth failed: {self.error}")
        if not self.code:
            raise RuntimeError("Gmail OAuth did not return an authorization code.")
        return self.code

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _random_verifier() -> str:
    return secrets.token_urlsafe(64)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
