"""Google API auth for the analytics readers.

Both Search Console and GA4 are read with the *same* service account the swarm
already uses for Vertex (`GOOGLE_APPLICATION_CREDENTIALS`), so onboarding a
tenant means granting two roles rather than minting new secrets.

Raw REST over `AuthorizedSession` is deliberate. Each API is used for exactly
one POST endpoint; `google-api-python-client` would add a large dependency and
a discovery-document round trip to save nothing.
"""
from __future__ import annotations

import os
from typing import Any

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

# Google rejects a request whose deadline it cannot meet anyway; a bounded
# timeout keeps a hung ingest from wedging the daily job forever.
REQUEST_TIMEOUT = 120


class AnalyticsAuthError(RuntimeError):
    """Credentials are missing or unusable. Never degrade to 'no data' silently —
    an empty result set is indistinguishable from a real zero-traffic day."""


def _credentials_path() -> str:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not path:
        raise AnalyticsAuthError(
            "GOOGLE_APPLICATION_CREDENTIALS is not set. Analytics ingestion needs the "
            "service account JSON that the rest of the swarm already uses."
        )
    if not os.path.exists(path):
        raise AnalyticsAuthError(
            f"Service account file not found at {path!r}. If it was moved, update "
            "GOOGLE_APPLICATION_CREDENTIALS in .env."
        )
    return path


def authorized_session(scope: str) -> Any:
    """An `AuthorizedSession` that refreshes its own token, scoped to one API."""
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - google-auth ships with the ADK
        raise AnalyticsAuthError(f"google-auth is not installed: {exc}") from exc

    path = _credentials_path()
    try:
        creds = service_account.Credentials.from_service_account_file(path, scopes=[scope])
    except Exception as exc:
        raise AnalyticsAuthError(f"Could not load service account from {path!r}: {exc}") from exc

    # Refresh eagerly. A service account file parses fine even when its key has
    # been deleted from IAM — the failure only appears at token exchange, which
    # would otherwise surface deep inside an unrelated API call as a bare
    # `invalid_grant`. One round trip buys an error that names the actual fix.
    try:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
    except Exception as exc:
        if "invalid_grant" in str(exc) or "Invalid JWT Signature" in str(exc):
            raise AnalyticsAuthError(
                f"The key in {path!r} is no longer valid for "
                f"{creds.service_account_email}. This means the key was deleted or "
                "rotated in IAM — the file itself is intact, so nothing local looks "
                "wrong. Create a new JSON key (IAM & Admin -> Service Accounts -> "
                "Keys -> Add key) and repoint GOOGLE_APPLICATION_CREDENTIALS at it."
            ) from exc
        raise AnalyticsAuthError(f"Could not obtain a token for {path!r}: {exc}") from exc

    return AuthorizedSession(creds)


def _credentials_field(field: str) -> str | None:
    import json

    try:
        with open(_credentials_path(), encoding="utf-8") as fh:
            return json.load(fh).get(field)
    except Exception:
        return None


def service_account_email() -> str | None:
    """The identity that must be granted access in Search Console and GA4.
    Surfaced in error messages so a 403 tells you *which* account to authorise.
    """
    return _credentials_field("client_email")


def project_id() -> str | None:
    """The GCP project the credentials belong to.

    Read from the key rather than hardcoded: the service account has already
    moved projects once ('buteforce' -> 'buteforec'), and an error message that
    names the wrong project sends you to enable an API that was never the
    problem.
    """
    return _credentials_field("project_id")


def explain_http_error(resp: Any, api: str) -> str:
    """Turn Google's JSON error body into something that names the fix.

    The two failures that actually happen in practice — API not enabled, and the
    service account not granted access — both surface as bare 403s whose default
    message sends people looking in the wrong place.
    """
    detail = ""
    try:
        detail = (resp.json().get("error", {}) or {}).get("message", "")
    except Exception:
        detail = (resp.text or "")[:400]

    hint = ""
    if resp.status_code == 403:
        email = service_account_email() or "the service account"
        if "SERVICE_DISABLED" in detail or "has not been used" in detail:
            hint = f" — enable the {api} API in Google Cloud project {project_id() or '(unknown)'!r}."
        else:
            hint = f" — grant {email} read access to the {api} property."
    elif resp.status_code == 404:
        hint = f" — check the {api} property identifier is exactly right."
    return f"{api} API {resp.status_code}: {detail}{hint}"
