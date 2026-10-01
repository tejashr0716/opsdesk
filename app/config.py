import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "opsdesk"
    db_password: str = ""
    db_name: str = "opsdesk"
    db_pool_size: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(override=False)
        pool = int(os.getenv("DB_POOL_SIZE", "8"))
        if not 1 <= pool <= 32:
            raise ValueError("DB_POOL_SIZE must be between 1 and 32")
        return cls(
            db_host=os.getenv("DB_HOST", "127.0.0.1"),
            db_port=int(os.getenv("DB_PORT", "3306")),
            db_user=os.getenv("DB_USER", "opsdesk"),
            db_password=os.getenv("DB_PASSWORD", ""),
            db_name=os.getenv("DB_NAME", "opsdesk"),
            db_pool_size=pool,
        )
