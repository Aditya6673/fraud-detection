"""
Redis caching service for fraud detection service.
"""

import json
import logging
from typing import Any, Dict, Optional, Union
import redis
from datetime import datetime, timedelta

from ..model.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis caching layer for fraud detection service.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
    ):
        """
        Initialize Redis connection.

        Args:
            host: Redis host. Defaults to settings.REDIS_HOST
            port: Redis port. Defaults to settings.REDIS_PORT
            db: Redis database. Defaults to settings.REDIS_DB
        """
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.db = db or settings.REDIS_DB
        self.client: Optional[redis.Redis] = None
        self.logger = logging.getLogger(__name__ + ".RedisCache")
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Test connection
            self.client.ping()
            self.logger.info(
                f"Connected to Redis at {self.host}:{self.port}, db={self.db}"
            )
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
            raise

    def is_connected(self) -> bool:
        """
        Check if Redis connection is active.

        Returns:
            bool: True if connected, False otherwise
        """
        if self.client is None:
            return False
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self.is_connected():
            return None

        try:
            value = self.client.get(key)
            if value is None:
                return None
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Return as string if not JSON
                return value
        except redis.RedisError as e:
            self.logger.error(f"Redis GET error for key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds. If None, uses default based on key type

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Serialize value to JSON if possible
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)

            # Determine TTL
            if ttl is None:
                ttl = self._get_default_ttl(key)

            # Set with expiration
            result = self.client.setex(key, ttl, serialized_value)
            self.logger.debug(f"Cached key {key} with TTL {ttl}s")
            return bool(result)

        except redis.RedisError as e:
            self.logger.error(f"Redis SET error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key was deleted, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            result = self.client.delete(key)
            return bool(result)
        except redis.RedisError as e:
            self.logger.error(f"Redis DELETE error for key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            bool: True if key exists, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            return bool(self.client.exists(key))
        except redis.RedisError as e:
            self.logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for key.

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            bool: True if expiration was set, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            result = self.client.expire(key, ttl)
            return bool(result)
        except redis.RedisError as e:
            self.logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False

    def _get_default_ttl(self, key: str) -> int:
        """
        Get default TTL based on key pattern.

        Args:
            key: Cache key

        Returns:
            TTL in seconds
        """
        if key.startswith("txn:features:"):
            return settings.FEATURE_CACHE_TTL
        elif key.startswith("txn:score:"):
            return settings.SCORE_CACHE_TTL
        elif key.startswith("model:"):
            return 86400  # 24 hours for model metadata
        else:
            return 300  # Default 5 minutes

    # Specific caching methods for fraud detection service

    def cache_transaction_features(
        self, transaction_id: str, features: Dict[str, Any]
    ) -> bool:
        """
        Cache extracted features for a transaction.

        Args:
            transaction_id: Unique transaction identifier
            features: Feature dictionary

        Returns:
            bool: True if cached successfully
        """
        key = f"txn:features:{transaction_id}"
        return self.set(key, features, settings.FEATURE_CACHE_TTL)

    def get_transaction_features(
        self, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached features for a transaction.

        Args:
            transaction_id: Unique transaction identifier

        Returns:
            Cached feature dictionary or None
        """
        key = f"txn:features:{transaction_id}"
        return self.get(key)

    def cache_transaction_score(
        self, transaction_id: str, score_data: Dict[str, Any]
    ) -> bool:
        """
        Cache scoring results for a transaction.

        Args:
            transaction_id: Unique transaction identifier
            score_data: Scoring result dictionary

        Returns:
            bool: True if cached successfully
        """
        key = f"txn:score:{transaction_id}"
        return self.set(key, score_data, settings.SCORE_CACHE_TTL)

    def get_transaction_score(
        self, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached scoring results for a transaction.

        Args:
            transaction_id: Unique transaction identifier

        Returns:
            Cached score dictionary or None
        """
        key = f"txn:score:{transaction_id}"
        return self.get(key)

    def cache_model_version(self, version: str) -> bool:
        """
        Cache the current model version.

        Args:
            version: Model version string

        Returns:
            bool: True if cached successfully
        """
        key = "model:version"
        return self.set(key, version, 86400)  # 24 hours

    def get_model_version(self) -> Optional[str]:
        """
        Get the cached model version.

        Returns:
            Model version string or None
        """
        key = "model:version"
        return self.get(key)

    def cache_model_load_timestamp(self) -> bool:
        """
        Cache the timestamp when the model was last loaded.

        Returns:
            bool: True if cached successfully
        """
        timestamp = datetime.now().isoformat()
        key = f"model:loaded:{timestamp}"
        return self.set(key, timestamp, 86400)  # 24 hours

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get Redis health status.

        Returns:
            Dictionary with health information
        """
        return {
            "connected": self.is_connected(),
            "host": self.host,
            "port": self.port,
            "db": self.db,
        }


# Helper function to create a cache instance
def create_redis_cache() -> RedisCache:
    """
    Factory function to create a Redis cache instance.

    Returns:
        Configured RedisCache instance
    """
    return RedisCache()