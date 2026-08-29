"""
Settings — the single source of truth for every environment variable this
app reads. See docs/projects/00-reference-app/spec.md §4.

WHAT: a typed, validated settings object built from environment variables
only. No config files, per the spec's twelve-factor rule — the same image
must run unchanged across docker-compose today and ten Kubernetes clusters
later, differing only in which env vars are injected.

WHO READS IT: every module in this app imports `settings` from here rather
than calling os.environ directly. That's deliberate — one place to see
every setting the app depends on, and pydantic validates types at startup
instead of the app crashing confusingly on the first request that touches
a malformed value.

FAILS: at process startup, loudly, if a required variable is missing or
the wrong type — e.g. POSTGRES_PORT="abc" raises immediately, not on the
first request that opens a connection.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- Identity (spec §3.4 /info, §4) ---
    service_name: str = "reference-api"
    app_version: str = "0.1.0"
    git_commit: str = "unknown"
    build_time: str = "unknown"
    environment: str = "dev"
    region: str = "local"
    tier: int = 1

    # --- Logging (spec §4) ---
    log_level: str = "INFO"
    log_format: str = "console"  # "console" locally, "json" everywhere else

    # --- Postgres — split into parts, never a single DATABASE_URL.
    # Only postgres_password is secret; the rest is safe to see in a
    # ConfigMap. See spec §4 for why that split matters. ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "referenceapp"
    postgres_user: str = "referenceapp"
    postgres_password: str = "changeme"

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_timeout_s: int = 5

    # --- Readiness (spec §3.2) ---
    ready_timeout_ms: int = 500
    ready_check_migrations: bool = True

    # --- Chaos / load endpoints (spec §3.5, §3.6) ---
    enable_chaos_endpoints: bool = False
    work_max_ms: int = 10_000

    # --- Server ---
    uvicorn_workers: int = 2

    @property
    def database_url(self) -> str:
        """Assembled only in-process for SQLAlchemy — never itself an env
        var, so it never has to be treated as the secret; only the
        password component does."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
