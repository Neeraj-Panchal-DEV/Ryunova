#backend/app/config.py

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = "postgresql+psycopg://ryunova:ryunova@localhost:5432/ryunova"
    secret_key: str = "dev-change-me-use-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://127.0.0.1:8001,http://localhost:8001"
    upload_dir: Path = Path("./uploads")
    media_url_prefix: str = "/api/v1/media"
    # JSON absolute URLs for API host; set API_PUBLIC_URL in production .env
    api_public_url: str = Field(default="http://127.0.0.1:8000", alias="API_PUBLIC_URL")
    # When set, public_media_url() uses this base (S3/CloudFront) instead of api_public_url + /api/v1/media
    media_public_base_url: str = Field(default="", alias="MEDIA_PUBLIC_BASE_URL")
    # Production bucket arn:aws:s3:::ryunova-channels-organisations-media — used when wiring boto3 uploads
    aws_s3_media_bucket: str = Field(default="", alias="AWS_S3_MEDIA_BUCKET")
    aws_s3_region: str = Field(default="", alias="AWS_S3_REGION")
    # When false (default), all media stays on local disk under upload_dir. When true, keys under orgs/ go to S3.
    use_s3_media: bool = Field(default=False, alias="USE_S3_MEDIA")

    # Optional SMTP for sign-in codes (same env names as Django web app; leave blank to log only)
    email_host: str = Field(default="", alias="EMAIL_HOST")
    email_port: int = Field(default=587, alias="EMAIL_PORT")
    email_use_tls: bool = Field(default=True, alias="EMAIL_USE_TLS")
    email_use_ssl: bool = Field(default=False, alias="EMAIL_USE_SSL")
    email_host_user: str = Field(default="", alias="EMAIL_HOST_USER")
    email_host_password: str = Field(default="", alias="EMAIL_HOST_PASSWORD")
    default_from_email: str = Field(default="", alias="DEFAULT_FROM_EMAIL")
    email_host_user_name: str = Field(
        default="Dragon and Peaches — RyuNova Platform",
        alias="EMAIL_HOST_USER_NAME",
    )
    site_url: str = Field(default="http://127.0.0.1:8001", alias="SITE_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.email_host_user.strip() and self.email_host_password.strip() and self.email_host.strip())

    @property
    def from_email_address(self) -> str:
        return (self.default_from_email or self.email_host_user or "noreply@localhost").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
