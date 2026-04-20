"""
Configuration loader — reads credentials from environment variables only.
No secrets are ever hardcoded or logged.
"""
import os
from dataclasses import dataclass, field


QUEUE_ID = 29682833  # Level 1 Support — hardcoded per spec


@dataclass
class Config:
    anthropic_api_key: str
    autotask_base_url: str
    autotask_username: str
    autotask_secret: str
    autotask_integration_code: str
    queue_id: int = field(default=QUEUE_ID)

    def __repr__(self) -> str:
        # Never expose secrets in repr/logs
        return (
            f"Config(username={self.autotask_username!r}, "
            f"base_url={self.autotask_base_url!r}, queue_id={self.queue_id})"
        )


def load_config() -> Config:
    """Load and validate required environment variables."""
    required: dict[str, str] = {
        "ANTHROPIC_API_KEY": "Anthropic API key",
        "AUTOTASK_BASE_URL": "Autotask REST base URL",
        "AUTOTASK_USERNAME": "Autotask username / email",
        "AUTOTASK_SECRET": "Autotask API secret",
        "AUTOTASK_INTEGRATION_CODE": "Autotask integration code",
    }

    missing = [k for k, label in required.items() if not os.getenv(k)]
    if missing:
        labels = [f"  • {k} ({required[k]})" for k in missing]
        raise EnvironmentError(
            "Missing required environment variables:\n" + "\n".join(labels)
        )

    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        autotask_base_url=os.environ["AUTOTASK_BASE_URL"].rstrip("/"),
        autotask_username=os.environ["AUTOTASK_USERNAME"],
        autotask_secret=os.environ["AUTOTASK_SECRET"],
        autotask_integration_code=os.environ["AUTOTASK_INTEGRATION_CODE"],
    )
