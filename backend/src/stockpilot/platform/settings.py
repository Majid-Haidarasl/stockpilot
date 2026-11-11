"""Application settings loaded from environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "stockpilot"
    environment: str = Field(default="development", alias="STOCKPILOT_ENVIRONMENT")

    # Runtime DB role only (never the schema owner in default Compose).
    database_url: str = Field(
        default="postgresql+psycopg://stockpilot_app:changeme@postgres:5432/stockpilot",
        alias="STOCKPILOT_DATABASE_URL",
    )
    expected_schema_revision: str = Field(
        default="0003_catalog_customers_rls",
        alias="STOCKPILOT_EXPECTED_SCHEMA_REVISION",
    )

    # Public issuer must match what the browser sees (do not disable issuer checks).
    oidc_issuer: str = Field(
        default="http://localhost:8180/realms/stockpilot",
        alias="STOCKPILOT_OIDC_ISSUER",
    )
    # Internal metadata/JWKS base used by the API container (may differ from issuer host).
    oidc_metadata_url: str = Field(
        default="http://keycloak:8080/realms/stockpilot/.well-known/openid-configuration",
        alias="STOCKPILOT_OIDC_METADATA_URL",
    )
    oidc_client_id: str = Field(default="stockpilot-api", alias="STOCKPILOT_OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(
        default="stockpilot-dev-client-secret-change-me",
        alias="STOCKPILOT_OIDC_CLIENT_SECRET",
    )
    oidc_redirect_uri: str = Field(
        default="http://localhost:8200/auth/callback",
        alias="STOCKPILOT_OIDC_REDIRECT_URI",
    )
    oidc_allowed_redirect_uris: str = Field(
        default="http://localhost:8200/auth/callback",
        alias="STOCKPILOT_OIDC_ALLOWED_REDIRECT_URIS",
    )

    session_cookie_name: str = Field(
        default="stockpilot_session",
        alias="STOCKPILOT_SESSION_COOKIE_NAME",
    )
    csrf_cookie_name: str = Field(
        default="stockpilot_csrf",
        alias="STOCKPILOT_CSRF_COOKIE_NAME",
    )
    cookie_secure: bool = Field(default=False, alias="STOCKPILOT_COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", alias="STOCKPILOT_COOKIE_SAMESITE")
    session_idle_minutes: int = Field(default=30, alias="STOCKPILOT_SESSION_IDLE_MINUTES")
    session_max_hours: int = Field(default=8, alias="STOCKPILOT_SESSION_MAX_HOURS")

    # Fernet key (url-safe base64, 32 bytes). Outside the database.
    token_encryption_key: str = Field(
        default="dev-only-fernet-key-32bytes-long!!",
        alias="STOCKPILOT_TOKEN_ENCRYPTION_KEY",
    )

    cors_origins: str = Field(
        default="http://localhost:5173",
        alias="STOCKPILOT_CORS_ORIGINS",
    )
    frontend_default_url: str = Field(
        default="http://localhost:5173",
        alias="STOCKPILOT_FRONTEND_DEFAULT_URL",
    )
    app_public_origin: str = Field(
        default="http://localhost:8200",
        alias="STOCKPILOT_APP_PUBLIC_ORIGIN",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def allowed_redirect_uri_list(self) -> list[str]:
        return [part.strip() for part in self.oidc_allowed_redirect_uris.split(",") if part.strip()]


def get_settings() -> Settings:
    return Settings()
