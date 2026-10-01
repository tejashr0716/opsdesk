from contextlib import contextmanager
from uuid import uuid4

from mysql.connector.pooling import MySQLConnectionPool

from app.config import Settings


class Database:
    """Blocking MySQL driver: FastAPI runs these calls in a threadpool."""

    def __init__(self, settings: Settings):
        self.pool = MySQLConnectionPool(
            pool_name=f"ops_{uuid4().hex[:12]}",
            pool_size=settings.db_pool_size,
            pool_reset_session=True,
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            connection_timeout=5,
            autocommit=False,
            charset="utf8mb4",
        )

    @contextmanager
    def connection(self):
        connection = self.pool.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET time_zone = '+00:00'")
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
