"""Application configuration loaded from environment."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:////data/alerts.db"
    data_dir: str = "/data"

    # Cloudflare Access. If aud is empty we skip JWT verification (local dev).
    cf_access_team_domain: str = ""
    cf_access_aud: str = ""

    # Gmail OAuth (Google Cloud project credentials)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # Public origin for the OAuth callback (must match the redirect URI
    # registered in Google Cloud Console). Empty = derive from request host
    # at OAuth-start time.
    public_base_url: str = ""

    # Gmail polling
    poll_interval_minutes: int = 30
    # How many days back to scan when polling. Bounds the query cost.
    gmail_lookback_days: int = 7

    # Nightly SQLite backup (server local time, 0-23)
    backup_hour: int = 4
    backup_keep_days: int = 30

    # Retention for the item cache (0 = keep forever).
    # Saved rows are never pruned.
    item_retention_days: int = 180

    log_level: str = "INFO"


settings = Settings()
