"""
Model loading and persistence components.
"""

import joblib
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


class FraudDetectionModel:
    """
    Handles loading, versioning, and prediction for fraud detection models.
    """

    def __init__(self, model_dir: Optional[str] = None):
        """
        Initialize the model loader.

        Args:
            model_dir: Directory containing model files. Defaults to settings.MODEL_DIR
        """
        self.model_dir = Path(model_dir) if model_dir else Path(settings.MODEL_DIR)
        self.model: Optional[Any] = None
        self.preprocessing_pipeline: Optional[Any] = None
        self.model_version: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self._is_loaded = False

        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def load_model(self, version: Optional[str] = None) -> bool:
        """
        Load a model from disk.

        Args:
            version: Specific version to load. If None, loads the latest version.

        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        try:
            if version is None:
                # Load latest version
                model_path = self._get_latest_model_path()
            else:
                # Load specific version
                model_path = self.model_dir / f"model_v{version}.joblib"
                metadata_path = self.model_dir / f"metadata_v{version}.joblib"

            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False

            # Load model
            self.model = joblib.load(model_path)
            logger.info(f"Loaded model from {model_path}")

            # Load metadata if exists
            metadata_path = model_path.with_name(model_path.name.replace("model_", "metadata_"))
            if metadata_path.exists():
                self.metadata = joblib.load(metadata_path)
                self.model_version = self.metadata.get("version", version or "unknown")
                logger.info(f"Loaded model metadata: {self.metadata}")
            else:
                self.model_version = version or "unknown"
                logger.warning(f"No metadata found for model {model_path}")

            # Load preprocessing pipeline if exists
            pipeline_path = model_path.with_name(model_path.name.replace("model_", "pipeline_"))
            if pipeline_path.exists():
                self.preprocessing_pipeline = joblib.load(pipeline_path)
                logger.info(f"Loaded preprocessing pipeline from {pipeline_path}")

            self._is_loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._is_loaded = False
            return False

    def predict(self, features: Any) -> Any:
        """
        Generate predictions using the loaded model.

        Args:
            features: Input features for prediction

        Returns:
            Model predictions (risk scores)

        Raises:
            RuntimeError: If model is not loaded
        """
        if not self.is_available():
            raise RuntimeError("Model is not loaded. Call load_model() first.")

        try:
            # Apply preprocessing pipeline if available
            if self.preprocessing_pipeline is not None:
                processed_features = self.preprocessing_pipeline.transform(features)
            else:
                processed_features = features

            # Get prediction probabilities
            if hasattr(self.model, "predict_proba"):
                # For classifiers, return probability of positive class (fraud)
                probabilities = self.model.predict_proba(processed_features)
                # Assuming binary classification: [prob_not_fraud, prob_fraud]
                risk_scores = probabilities[:, 1] * 100  # Convert to 0-100 scale
            else:
                # For regressors or other models
                raw_predictions = self.model.predict(processed_features)
                # Assuming output is already in 0-1 range or needs scaling
                risk_scores = raw_predictions * 100

            return risk_scores

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def get_version(self) -> Optional[str]:
        """
        Get the version of the currently loaded model.

        Returns:
            str: Model version or None if not loaded
        """
        return self.model_version

    def is_available(self) -> bool:
        """
        Check if a model is currently loaded and ready for predictions.

        Returns:
            bool: True if model is available, False otherwise
        """
        return self._is_loaded and self.model is not None

    def _get_latest_model_path(self) -> Path:
        """
        Find the latest model file in the model directory.

        Returns:
            Path: Path to the latest model file
        """
        model_files = list(self.model_dir.glob("model_v*.joblib"))
        if not model_files:
            raise FileNotFoundError(f"No model files found in {self.model_dir}")

        # Sort by version number (assuming semantic versioning)
        def extract_version(path: Path) -> tuple:
            # Extract version from filename like model_v1.2.3.joblib
            try:
                version_str = path.stem.split("_v")[1]
                return tuple(map(int, version_str.split(".")))
            except (IndexError, ValueError):
                return (0, 0, 0)  # Default to oldest if parsing fails

        latest_model = max(model_files, key=extract_version)
        return latest_model

    def list_available_models(self) -> list:
        """
        List all available model versions.

        Returns:
            list: List of available model versions
        """
        model_files = list(self.model_dir.glob("model_v*.joblib"))
        versions = []
        for model_file in model_files:
            try:
                version_str = model_file.stem.split("_v")[1]
                versions.append(version_str)
            except IndexError:
                pass
        return sorted(versions, key=lambda v: tuple(map(int, v.split("."))))

    def save_model(
        self,
        model: Any,
        preprocessing_pipeline: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
    ) -> str:
        """
        Save a model to disk.

        Args:
            model: Trained model to save
            preprocessing_pipeline: Fitted preprocessing pipeline
            metadata: Model metadata (training date, metrics, etc.)
            version: Version string. If None, auto-increment based on existing models

        Returns:
            str: Version of the saved model
        """
        if version is None:
            # Auto-increment version
            existing_versions = self.list_available_models()
            if existing_versions:
                # Parse versions and increment the latest
                parsed_versions = [tuple(map(int, v.split("."))) for v in existing_versions]
                latest_version = max(parsed_versions)
                new_version = f"{latest_version[0]}.{latest_version[1]}.{latest_version[2] + 1}"
            else:
                new_version = "1.0.0"
        else:
            new_version = version

        # Save model
        model_path = self.model_dir / f"model_v{new_version}.joblib"
        joblib.dump(model, model_path)
        logger.info(f"Saved model to {model_path}")

        # Save preprocessing pipeline
        if preprocessing_pipeline is not None:
            pipeline_path = self.model_dir / f"pipeline_v{new_version}.joblib"
            joblib.dump(preprocessing_pipeline, pipeline_path)
            logger.info(f"Saved preprocessing pipeline to {pipeline_path}")

        # Save metadata
        if metadata is None:
            metadata = {}
        metadata.update(
            {
                "version": new_version,
                "model_type": type(model).__name__,
            }
        )

        metadata_path = self.model_dir / f"metadata_v{new_version}.joblib"
        joblib.dump(metadata, metadata_path)
        logger.info(f"Saved model metadata to {metadata_path}")

        return new_version