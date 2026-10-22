import asyncio
import time
from typing import Any, AsyncGenerator, Dict, Optional
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.db.mongodb")


class MongoManager:
    """
    Manages MongoDB connection lifecycle and provides database access
    using PyMongo's asynchronous API (AsyncMongoClient).
    """

    def __init__(self) -> None:
        self.client: Optional[AsyncMongoClient] = None
        self.db: Optional[AsyncDatabase] = None
        self.is_connected: bool = False

    async def connect(self) -> None:
        """
        Initialize the AsyncMongoClient and attempt to connect to MongoDB.
        """
        logger.info(
            "Initializing MongoDB async client (URL: %s, Database: %s)",
            settings.MONGODB_URL.split("@")[-1],  # Avoid logging credentials if in URI
            settings.DATABASE_NAME,
        )
        try:
            self.client = AsyncMongoClient(
                settings.MONGODB_URL,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            )
            self.db = self.client[settings.DATABASE_NAME]

            # Verify connection with an initial ping (short wait so startup is not blocked)
            try:
                await asyncio.wait_for(self.client.admin.command("ping"), timeout=2.0)
                self.is_connected = True
                logger.info("Successfully connected to MongoDB database: %s", settings.DATABASE_NAME)
            except (asyncio.TimeoutError, ConnectionFailure, ServerSelectionTimeoutError) as ping_err:
                self.is_connected = False
                logger.warning(
                    "MongoDB ping failed at startup (%s). Application running in degraded database mode.",
                    type(ping_err).__name__,
                )
        except Exception as exc:
            self.is_connected = False
            logger.error("Unexpected error initializing MongoDB client: %s", exc, exc_info=True)

    async def close(self) -> None:
        """
        Gracefully close MongoDB client connections.
        """
        if self.client:
            logger.info("Closing MongoDB connections...")
            await self.client.close()
            self.is_connected = False
            logger.info("MongoDB connection closed.")

    async def ping(self, timeout_seconds: float = 1.5) -> Dict[str, Any]:
        """
        Execute a ping command to verify database connectivity and measure latency.
        """
        if not self.client:
            return {
                "connected": False,
                "error": "Client not initialized",
                "database": settings.DATABASE_NAME,
            }

        start_time = time.perf_counter()
        try:
            await asyncio.wait_for(self.client.admin.command("ping"), timeout=timeout_seconds)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.is_connected = True
            return {
                "connected": True,
                "latency_ms": latency_ms,
                "database": settings.DATABASE_NAME,
            }
        except (asyncio.TimeoutError, ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as exc:
            self.is_connected = False
            error_desc = str(exc).strip() or "Connection timed out"
            return {
                "connected": False,
                "error": f"{type(exc).__name__}: {error_desc}",
                "database": settings.DATABASE_NAME,
            }

    def get_database(self) -> AsyncDatabase:
        """
        Get the current active database instance.
        """
        if self.db is None:
            raise RuntimeError("Database not initialized. Please call connect() first.")
        return self.db


# Global manager instance
mongo_manager = MongoManager()


async def connect_to_mongo() -> None:
    """Helper function to connect at application startup."""
    await mongo_manager.connect()


async def close_mongo_connection() -> None:
    """Helper function to disconnect at application shutdown."""
    await mongo_manager.close()


def get_database() -> AsyncDatabase:
    """Helper function to access the MongoDB database instance."""
    return mongo_manager.get_database()


async def get_db() -> AsyncGenerator[AsyncDatabase, None]:
    """
    FastAPI dependency that yields the MongoDB AsyncDatabase.
    """
    yield mongo_manager.get_database()
