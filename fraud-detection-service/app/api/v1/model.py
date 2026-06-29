"""
Model management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Any, Dict, Optional
import json

from ...model.loader import FraudDetectionModel
from ...services.redis_cache import RedisCache

router = APIRouter()


def get_model_loader() -> FraudDetectionModel:
    """Dependency to get model loader instance."""
    from ...main import model_loader

    if model_loader is None:
        raise HTTPException(
            status_code=503, detail="Model loader not initialized"
        )
    return model_loader


def get_redis_cache() -> RedisCache:
    """Dependency to get Redis cache instance."""
    from ...main import redis_cache

    if redis_cache is None:
        raise HTTPException(
            status_code=503, detail="Redis cache not initialized"
        )
    return redis_cache


@router.get("/info", response_model=Dict[str, Any])
async def get_model_info(
    loader: FraudDetectionModel = Depends(get_model_loader),
) -> Dict[str, Any]:
    """
    Get information about the current model.

    Returns:
        Model metadata and version information
    """
    try:
        info = {
            "available": loader.is_available(),
            "version": loader.get_version(),
        }

        if loader.is_available():
            info["metadata"] = loader.metadata
            info["available_versions"] = loader.list_available_models()

        return info

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get model info: {str(e)}"
        )


@router.post("/reload", response_model=Dict[str, Any])
async def reload_model(
    background_tasks: BackgroundTasks,
    version: Optional[str] = None,
    loader: FraudDetectionModel = Depends(get_model_loader),
    cache: RedisCache = Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Reload the ML model (hot-reload without downtime).

    Args:
        version: Specific version to load. If None, loads latest version.
        background_tasks: FastAPI background tasks
        loader: Model loader dependency
        cache: Redis cache dependency

    Returns:
        Status of the reload operation
    """
    try:
        # Run reload in background to avoid blocking
        def reload_task():
            try:
                logger.info(f"Attempting to reload model (version: {version})")
                success = loader.load_model(version=version)
                if success:
                    logger.info(
                        f"Successfully reloaded model version: {loader.get_version()}"
                    )
                    # Update cache
                    cache.cache_model_version(loader.get_version() or "unknown")
                else:
                    logger.error("Failed to reload model")
            except Exception as e:
                logger.error(f"Error during model reload: {e}")

        background_tasks.add_task(reload_task)

        return {
            "status": "reload_initiated",
            "message": "Model reload started in background",
            "version_requested": version,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate model reload: {str(e)}"
        )


@router.get("/versions", response_model=Dict[str, Any])
async def list_model_versions(
    loader: FraudDetectionModel = Depends(get_model_loader),
) -> Dict[str, Any]:
    """
    List all available model versions.

    Returns:
        List of available model versions
    """
    try:
        versions = loader.list_available_models()
        return {
            "available_versions": versions,
            "current_version": loader.get_version(),
            "count": len(versions),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list model versions: {str(e)}"
        )


# Import logger and Optional
import logging
from typing import Optional

logger = logging.getLogger(__name__)