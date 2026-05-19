"""Unwrap Google Alerts redirect URLs.

Google Alerts wraps every link in `https://www.google.com/url?...&url=<real>&...`.
We extract the real `url` query parameter so the app links straight to the source.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse


_GOOGLE_REDIRECT_HOSTS = {"www.google.com", "google.com", "news.google.com"}


def unwrap(link: str) -> str:
    """Return the underlying target URL, or `link` unchanged if not wrapped."""
    if not link:
        return ""
    try:
        parsed = urlparse(link)
    except ValueError:
        return link
    if parsed.netloc not in _GOOGLE_REDIRECT_HOSTS:
        return link
    if parsed.path not in ("/url", "/alerts/atom"):
        return link
    qs = parse_qs(parsed.query)
    # `url` is the canonical key; `q` is used by some news redirects.
    for key in ("url", "q"):
        vals = qs.get(key)
        if vals and vals[0]:
            return vals[0]
    return link


def source_domain(link: str) -> str:
    """Bare-domain extract, `www.` stripped."""
    try:
        netloc = urlparse(link).netloc.lower()
    except ValueError:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc
