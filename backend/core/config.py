"""
Backend configuration.

Config priority:
1. Process environment and mounted env file (process environment wins)
2. Apollo HTTP config, when APOLLO_ENABLED=true
3. Code defaults
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _load_env_dir(env_dir: Path):
    loaded = 0
    for item in env_dir.iterdir():
        if not item.is_file() or item.name.startswith("."):
            continue
        os.environ.setdefault(item.name, item.read_text(encoding="utf-8").strip())
        loaded += 1
    logger.info("Loaded %d env values from dir: %s", loaded, env_dir)


def _load_env_file():
    env_path = os.getenv("ENV_FILE") or os.getenv("CONF_FILE_PATH")
    if not env_path:
        env_path = "/app/.env" if Path("/app/.env").exists() else ".env"

    env_path = Path(env_path)
    if env_path.is_dir():
        _load_env_dir(env_path)
        return

    load_dotenv(dotenv_path=env_path, override=False)
    logger.info("Loaded env file: %s", env_path)


def _load_apollo_config():
    if os.getenv("APOLLO_ENABLED", "false").lower() != "true":
        return

    server = os.getenv("APOLLO_SERVER_URL", "http://apollo-config:8080")
    app_id = os.getenv("APOLLO_APP_ID", "smart-test-backend")
    cluster = os.getenv("APOLLO_CLUSTER", "default")
    namespace = os.getenv("APOLLO_NAMESPACE", "application")

    url = f"{server}/configfiles/json/{app_id}/{cluster}/{namespace}"
    try:
        import httpx

        with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            config = resp.json()
            for key, value in config.items():
                if isinstance(value, str):
                    os.environ[key] = value
            logger.info(
                "Apollo loaded %d config values (app=%s cluster=%s ns=%s)",
                len(config),
                app_id,
                cluster,
                namespace,
            )
    except Exception as exc:
        logger.warning("Apollo load failed, using local env config: %s", exc)


_load_env_file()
_load_apollo_config()


class Settings(BaseSettings):
    APP_TITLE: str = os.getenv("APP_TITLE", "Smart Test")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    ENABLE_API_DOCS: bool = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+asyncmy://root:password@localhost:3306/st_smart_test",
    )
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "st_smart_test")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "zhi-ce-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER", "10080")
    )

    # 前端可访问地址，可带子路径前缀（如 https://host/tc-smart-test-frontend）；
    # 留空表示未配置，手动发送报告时按请求来源自动识别
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "")
    BACKEND_CORS_ORIGINS: str = os.getenv("BACKEND_CORS_ORIGINS", "*")
    AMAP_WEB_SERVICE_KEY: str = os.getenv("AMAP_WEB_SERVICE_KEY", "")
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_POLL_SECONDS: int = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))
    SCHEDULER_MAX_CONCURRENT: int = int(os.getenv("SCHEDULER_MAX_CONCURRENT", "3"))
    SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES: int = int(os.getenv("SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES", "3"))
    AI_PLATFORM_MAX_CONCURRENT: int = int(os.getenv("AI_PLATFORM_MAX_CONCURRENT", "3"))

    # Windows 盘符挂载根路径（Docker 内 /mnt/c、/mnt/d 的前缀，macOS/Linux 不适用）
    FILE_MOUNT_ROOT: str = os.getenv("FILE_MOUNT_ROOT", "/mnt")

    class Config:
        case_sensitive = True

    def get_cors_origins(self) -> list[str]:
        if self.BACKEND_CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
