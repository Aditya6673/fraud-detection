"""
Main application entry point for fraud detection service.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .model.config import settings
from .model.loader import FraudDetectionModel
from .model.processor import TransactionFeatureProcessor
from .model.scorer import FraudScoringEngine
from .services.kafka_consumer import KafkaTransactionConsumer
from .services.redis_cache import RedisCache
from .api.v1 import scoring, model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
model_loader: Optional[FraudDetectionModel] = None
feature_processor: Optional[TransactionFeatureProcessor] = None
scoring_engine: Optional[FraudScoringEngine] = None
kafka_consumer: Optional[KafkaTransactionConsumer] = None
redis_cache: Optional[RedisCache] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    global model_loader, feature_processor, scoring_engine, kafka_consumer, redis_cache

    logger.info("Starting Fraud Detection Service...")

    try:
        # Initialize components
        logger.info("Initializing components...")
        model_loader = FraudDetectionModel()
        feature_processor = TransactionFeatureProcessor()
        scoring_engine = FraudScoringEngine(
            model_loader=model_loader,
            feature_processor=feature_processor,
            risk_threshold_low=settings.RISK_THRESHOLD_LOW,
            risk_threshold_high=settings.RISK_THRESHOLD_HIGH,
        )
        redis_cache = RedisCache()
        kafka_consumer = KafkaTransactionConsumer(
            scoring_engine=scoring_engine,
            message_handler=_handle_scored_transaction,
        )

        # Attempt to load model
        logger.info("Loading ML model...")
        if not model_loader.load_model():
            logger.warning(
                "Failed to load ML model. Service will use fallback scoring."
            )
        else:
            logger.info(
                f"Successfully loaded model version: {model_loader.get_version()}"
            )

        # Start Kafka consumer in background
        logger.info("Starting Kafka consumer...")
        kafka_consumer.start()

        logger.info("Fraud Detection Service started successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down Fraud Detection Service...")
        if kafka_consumer:
            kafka_consumer.stop()
        logger.info("Fraud Detection Service stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Service for scoring transactions for fraud risk",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
)

# Add CORS middleware
allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)


# Dependency injection
def get_model_loader() -> FraudDetectionModel:
    """Dependency to get model loader instance."""
    if model_loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")
    return model_loader


def get_scoring_engine() -> FraudScoringEngine:
    """Dependency to get scoring engine instance."""
    if scoring_engine is None:
        raise HTTPException(status_code=503, detail="Scoring engine not initialized")
    return scoring_engine


def get_redis_cache() -> RedisCache:
    """Dependency to get Redis cache instance."""
    if redis_cache is None:
        raise HTTPException(status_code=503, detail="Redis cache not initialized")
    return redis_cache


# Include API routers
app.include_router(scoring.router, prefix="/api/v1/score", tags=["scoring"])
app.include_router(model.router, prefix="/api/v1/model", tags=["model"])


# Root endpoint
@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Fraud Detection Service is running",
        "version": settings.SERVICE_VERSION,
    }


# Health check endpoint
@app.get("/health")
async def health_check(
    model_loader: FraudDetectionModel = Depends(get_model_loader),
    redis_cache: RedisCache = Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Health check endpoint.
    Returns overall service health including component status.
    """
    health_status = {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "model": {
                "available": model_loader.is_available(),
                "version": model_loader.get_version(),
            },
            "kafka": {
                "running": kafka_consumer is not None and kafka_consumer.running
                if kafka_consumer
                else False,
            },
            "redis": redis_cache.get_health_status(),
        },
    }

    # Determine overall health
    if not model_loader.is_available() and not settings.FALLBACK_TO_RULES:
        health_status["status"] = "degraded"
        health_status["details"] = "ML model unavailable and fallback disabled"

    return health_status


def _handle_scored_transaction(result: Dict[str, Any]) -> None:
    """
    Handle a scored transaction from the Kafka consumer.

    Args:
        result: Scoring result dictionary
    """
    # This function is called by the Kafka consumer when a transaction is scored
    # In a full implementation, you might:
    # 1. Publish results to a "fraud-scores" Kafka topic
    # 2. Store results in a database for analytics
    # 3. Trigger alerts for high-risk transactions
    # 4. Update dashboards or monitoring systems

    logger.debug(
        f"Handling scored transaction: {result['transactionId']} "
        f"score={result['riskScore']:.1f} level={result['riskLevel']}"
    )

    # Example: Publish to fraud-scores topic (would need Kafka producer)
    # Example: Store in database for trend analysis
    # Example: Alert if score > 90

    # For now, we just log significant events
    if result["riskLevel"] == "BLOCKED":
        logger.warning(
            f"BLOCKED TRANSACTION: {result['transactionId']} "
            f"score={result['riskScore']:.1f} reasons={result['reasons']}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=os.getenv("ENVIRONMENT") == "development",
    )