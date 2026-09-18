"""LTI AGS HTTP client — OAuth2 client-credentials + score POST.

Dry-run by default (``GRADEVANCE_LTI_AGS_DRY_RUN=true``) so CI/dev never
hits a real LMS. Production: set token URL + client secret and dry_run=false.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings

from gradevance.lti.ags import AgsScore

logger = logging.getLogger(__name__)

# IMS AGS scopes commonly required for score write.
_DEFAULT_SCOPES = (
    "https://purl.imsglobal.org/spec/lti-ags/scope/score "
    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"
)


@dataclass
class AgsHttpResult:
    dry_run: bool
    ok: bool
    status_code: int | None
    url: str
    body: Any
    error: str = ""


def ags_score_json(score: AgsScore) -> dict[str, Any]:
    """IMS AGS score body (camelCase)."""
    payload: dict[str, Any] = {
        "userId": score.user_id,
        "scoreMaximum": score.score_maximum,
        "activityProgress": score.activity_progress,
        "gradingProgress": score.grading_progress,
    }
    if score.score_given is not None:
        payload["scoreGiven"] = score.score_given
    if score.comment:
        payload["comment"] = score.comment
    return payload


def _token_url() -> str:
    return (getattr(settings, "GRADEVANCE_LTI_TOKEN_URL", "") or "").strip()


def _client_secret() -> str:
    return (getattr(settings, "GRADEVANCE_LTI_CLIENT_SECRET", "") or "").strip()


def _dry_run() -> bool:
    return bool(getattr(settings, "GRADEVANCE_LTI_AGS_DRY_RUN", True))


def fetch_ags_access_token(
    *,
    token_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    scopes: str | None = None,
    timeout: float = 15.0,
) -> str:
    """Client-credentials grant for AGS. Raises ``AgsPassbackError`` on failure."""
    from gradevance.lti.ags import AgsPassbackError

    url = (token_url or _token_url()).strip()
    cid = (client_id or getattr(settings, "GRADEVANCE_LTI_CLIENT_ID", "") or "").strip()
    secret = (client_secret or _client_secret()).strip()
    if not url or not cid or not secret:
        raise AgsPassbackError(
            "AGS token settings incomplete (TOKEN_URL, CLIENT_ID, CLIENT_SECRET)"
        )
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
            "scope": scopes or _DEFAULT_SCOPES.strip(),
        },
        timeout=timeout,
        headers={"Accept": "application/json"},
    )
    if resp.status_code >= 400:
        raise AgsPassbackError(f"Token endpoint HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise AgsPassbackError("Token response missing access_token")
    return str(token)


def scores_url_for_lineitem(lineitem_url: str) -> str:
    """Append ``/scores`` to a lineitem URL (handles trailing slash)."""
    base = lineitem_url.rstrip("/") + "/"
    return urljoin(base, "scores")


def post_ags_score(
    *,
    lineitem_url: str,
    score: AgsScore,
    access_token: str | None = None,
    dry_run: bool | None = None,
    timeout: float = 15.0,
) -> AgsHttpResult:
    """POST score to LMS. When dry_run, returns payload without network I/O."""
    from gradevance.lti.ags import AgsPassbackError

    if not lineitem_url:
        raise AgsPassbackError("lineitem_url required")

    url = scores_url_for_lineitem(lineitem_url)
    body = ags_score_json(score)
    use_dry = _dry_run() if dry_run is None else dry_run

    if use_dry:
        logger.info("AGS dry-run POST %s body=%s", url, body)
        return AgsHttpResult(
            dry_run=True,
            ok=True,
            status_code=None,
            url=url,
            body={"would_post": body, "asdict": asdict(score)},
        )

    token = access_token or fetch_ags_access_token()
    resp = requests.post(
        url,
        json=body,
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.ims.lis.v1.score+json",
            "Accept": "application/json",
        },
    )
    ok = 200 <= resp.status_code < 300
    parsed: Any
    try:
        parsed = resp.json()
    except Exception:
        parsed = resp.text[:500]
    if not ok:
        logger.warning("AGS POST failed %s → %s %s", url, resp.status_code, parsed)
    return AgsHttpResult(
        dry_run=False,
        ok=ok,
        status_code=resp.status_code,
        url=url,
        body=parsed,
        error="" if ok else f"HTTP {resp.status_code}",
    )
