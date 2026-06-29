"""
Configuration management for fraud detection service.
"""

import os
from typing import Optional


class Settings:
    """Application settings."""

    def __init__(self):
        # Service configuration
        self.SERVICE_NAME: str = os.getenv("SERVICE_NAME", "fraud-detection-service")
        self.SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "0.1.0")
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Kafka configuration
        self.KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.KAFKA_TRANSACTIONS_TOPIC: str = os.getenv("KAFKA_TRANSACTIONS_TOPIC", "transactions")
        self.KAFKA_FRAUD_SCORES_TOPIC: str = os.getenv("KAFKA_FRAUD_SCORES_TOPIC", "fraud-scores")
        self.KAFKA_CONSUMER_GROUP_ID: str = os.getenv("KAFKA_CONSUMER_GROUP_ID", "fraud-detection-service")

        # Redis configuration
        self.REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
        self.REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

        # Model configuration
        self.MODEL_DIR: str = os.getenv("MODEL_DIR", "/app/models")
        self.MODEL_VERSION: str = os.getenv("MODEL_VERSION", "1.0.0")
        self.MODEL_LOAD_TIMEOUT: int = int(os.getenv("MODEL_LOAD_TIMEOUT", "30"))

        # Scoring thresholds
        self.RISK_THRESHOLD_LOW: float = float(os.getenv("RISK_THRESHOLD_LOW", "30.0"))
        self.RISK_THRESHOLD_HIGH: float = float(os.getenv("RISK_THRESHOLD_HIGH", "70.0"))

        # Caching TTL (in seconds)
        self.FEATURE_CACHE_TTL: int = int(os.getenv("FEATURE_CACHE_TTL", "300"))   # 5 minutes
        self.SCORE_CACHE_TTL: int = int(os.getenv("SCORE_CACHE_TTL", "3600"))    # 1 hour

        # Feature flags
        self.ENABLE_ML_SCORING: bool = os.getenv("ENABLE_ML_SCORING", "true").lower() == "true"
        self.FALLBACK_TO_RULES: bool = os.getenv("FALLBACK_TO_RULES", "true").lower() == "true"


# Global settings instance
settings = Settings()