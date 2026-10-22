"""Runtime configuration - every value comes from the environment.

Nothing is hardcoded here: the defaults are placeholders and can be changed in
.env (local) or docker-compose.yml (containers) without touching code.

Rules:
- LLM_API_KEY is a secret. It is never logged, never printed in an error and
  never baked into the image (see .dockerignore).
- Startup fails fast with a clear message when the environment cannot work.
Owner: DevOps 1.
"""
from functools import lru_cache
from typing import Dict, Tuple

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder values that still need confirmation from the team (see README).
PERIOD_SECONDS: Dict[str, int] = {
    "second": 1, "seconds": 1, "s": 1,
    "minute": 60, "minutes": 60, "min": 60, "m": 60,
    "hour": 3600, "hours": 3600, "hr": 3600,
    "day": 86400, "days": 86400, "d": 86400,
}
_LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET")
# Inbound authentication methods. "none" keeps the endpoint open (the default
# until the team confirms the method); "api_key" reads the X-API-Key header;
# "bearer" reads Authorization: Bearer <token>.
AUTH_METHODS = ("none", "api_key", "bearer")
# The dummy value that ships in .env.example. It is refused as a live
# credential so a copied template can never leave the endpoint open.
PLACEHOLDER_SECRET = "placeholder-not-a-real-key"


class SettingsError(RuntimeError):
    """Raised at startup when the environment is unusable."""


def parse_rate_limit(spec: str) -> Tuple[int, int]:
    """'30/minute' -> (30, 60): (allowed requests, window seconds)."""
    text = str(spec or "").strip().lower()
    count_text, _, period = text.partition("/")
    period = period or "minute"
    if not count_text.strip().isdigit():
        raise ValueError(f"invalid rate limit {spec!r}: expected '<count>/<period>' like 30/minute")
    count = int(count_text)
    if count < 1:
        raise ValueError(f"invalid rate limit {spec!r}: count must be at least 1")
    if period not in PERIOD_SECONDS:
        raise ValueError(f"invalid rate limit period {period!r}: use second, minute, hour or day")
    return count, PERIOD_SECONDS[period]


class Settings(BaseSettings):
    # .env is optional (docker-compose passes env vars instead); real env always wins.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM / orchestrator -------------------------------------------------
    # Secret. Required only when USE_MOCK=false; repr=False keeps it out of logs.
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_provider: str = "placeholder"
    llm_timeout_seconds: float = Field(default=10.0, gt=0)
    use_mock: bool = True

    # --- rate limiting (single instance; needs Redis if we scale out) -------
    rate_limit_per_user: str = "30/minute"
    rate_limit_per_ip: str = "60/minute"
    trusted_proxy: bool = False

    # --- response cache -----------------------------------------------------
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=600, ge=0)
    cache_max_items: int = Field(default=500, ge=1)

    # --- logging ------------------------------------------------------------
    log_level: str = "INFO"

    # --- inbound authentication (Day 4) ---------------------------------------
    # AUTH_METHOD: "none" (default - the endpoint stays open), "api_key"
    # (X-API-Key header) or "bearer" (Authorization: Bearer <token>).
    # The method is configurable so the team can switch to Bearer without a
    # code change - only the environment changes.
    auth_method: str = "none"
    # Secret. Required when AUTH_METHOD is not "none". Never logged, never
    # returned in an error, never committed (it comes from the environment).
    api_key: str | None = Field(default=None, repr=False)

    # --- not owned by this service, kept for the shared .env ---------------
    internal_api_key: str | None = Field(default=None, repr=False)

    @field_validator("rate_limit_per_user", "rate_limit_per_ip")
    @classmethod
    def _valid_rate_limit(cls, value: str) -> str:
        parse_rate_limit(value)
        return value

    @field_validator("auth_method")
    @classmethod
    def _valid_auth_method(cls, value: str) -> str:
        method = str(value or "none").strip().lower()
        if method not in AUTH_METHODS:
            raise ValueError(
                f"invalid AUTH_METHOD {value!r}: use one of {', '.join(AUTH_METHODS)}")
        return method

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        level = str(value).upper().strip()
        if level not in _LOG_LEVELS:
            raise ValueError(f"invalid LOG_LEVEL {value!r}: use one of {', '.join(_LOG_LEVELS)}")
        return level

    @model_validator(mode="after")
    def _require_api_key_for_real_mode(self):
        if not self.use_mock and not self.llm_api_key:
            raise ValueError(
                "LLM_API_KEY is required when USE_MOCK=false. "
                "Set it in the environment (see .env.example) or keep USE_MOCK=true."
            )
        return self

    @model_validator(mode="after")
    def _require_api_key_when_auth_is_on(self):
        if self.auth_method != "none" and not self.api_key:
            raise ValueError(
                f"API_KEY is required when AUTH_METHOD={self.auth_method}. "
                "Set it in the environment (see .env.example); it is never committed."
            )
        return self

    @model_validator(mode="after")
    def _reject_the_placeholder_key(self):
        # The value shipped in .env.example must never work as a live
        # credential - otherwise copying the template and flipping
        # AUTH_METHOD would silently open the endpoint with a guessable key.
        if self.auth_method != "none" and self.api_key == PLACEHOLDER_SECRET:
            raise ValueError(
                f"API_KEY is still the placeholder value ({PLACEHOLDER_SECRET}). "
                "Set a real secret in the environment before enabling "
                f"AUTH_METHOD={self.auth_method}."
            )
        return self

    # Parsed on demand; the raw strings above are validated at startup.
    @property
    def user_limit(self) -> Tuple[int, int]:
        return parse_rate_limit(self.rate_limit_per_user)

    @property
    def ip_limit(self) -> Tuple[int, int]:
        return parse_rate_limit(self.rate_limit_per_ip)


@lru_cache
def get_settings() -> Settings:
    """Cached settings. Fails fast with one clear line instead of a stack trace."""
    try:
        return Settings()
    except ValidationError as exc:
        reasons = "; ".join(str(err.get("msg", "invalid value")) for err in exc.errors())
        raise SettingsError(f"Invalid configuration: {reasons}") from None
