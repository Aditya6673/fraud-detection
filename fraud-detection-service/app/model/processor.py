"""
Feature engineering components for fraud detection service.
"""

import numpy as np
import logging
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TransactionFeatureProcessor:
    """
    Processes raw transaction data into features suitable for ML model inference.
    """

    def __init__(self):
        """Initialize the feature processor."""
        # Feature statistics for normalization (should match training)
        self.feature_means = None
        self.feature_stds = None
        self.is_fitted = False

    def fit(self, features: np.ndarray) -> None:
        """
        Compute feature statistics for normalization.

        Args:
            features: Training features to compute statistics from
        """
        self.feature_means = np.mean(features, axis=0)
        self.feature_stds = np.std(features, axis=0)
        # Avoid division by zero
        self.feature_stds = np.where(self.feature_stds == 0, 1, self.feature_stds)
        self.is_fitted = True
        logger.info(f"Fitted feature processor on {features.shape[0]} samples")

    def transform(self, features: np.ndarray) -> np.ndarray:
        """
        Normalize features using fitted statistics.

        Args:
            features: Features to normalize

        Returns:
            Normalized features
        """
        if not self.is_fitted:
            logger.warning("Feature processor not fitted. Returning features as-is.")
            return features

        return (features - self.feature_means) / self.feature_stds

    def fit_transform(self, features: np.ndarray) -> np.ndarray:
        """
        Fit to features, then transform them.

        Args:
            features: Features to fit and transform

        Returns:
            Normalized features
        """
        self.fit(features)
        return self.transform(features)

    def process_transaction(self, transaction: Dict[str, Any]) -> np.ndarray:
        """
        Convert a transaction dictionary to feature vector.

        Args:
            transaction: Transaction data matching ScoreRequest format

        Returns:
            Feature vector as numpy array
        """
        # Extract basic features
        features = []

        # Time feature (seconds since epoch or timestamp)
        timestamp_str = transaction.get("timestamp", "")
        try:
            # Parse ISO format timestamp
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            # Seconds since Unix epoch
            time_seconds = dt.timestamp()
        except (ValueError, AttributeError):
            # Fallback: use current time if parsing fails
            time_seconds = datetime.now().timestamp()

        features.append(time_seconds)

        # Amount feature
        amount = float(transaction.get("amount", 0.0))
        features.append(amount)

        # V1-V28 features (PCA components)
        # In a real implementation, these would come from feature engineering
        # For now, we'll use placeholder zeros - in production, these would be
        # computed from raw transaction data using the same PCA transformation
        # as used in the creditcard.csv dataset
        v_features = [0.0] * 28  # Placeholder for V1-V28
        features.extend(v_features)

        # Convert to numpy array and reshape for sklearn
        feature_array = np.array(features).reshape(1, -1)
        return feature_array

    def extract_temporal_features(self, timestamp_str: str) -> Dict[str, Any]:
        """
        Extract temporal features from timestamp.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            Dictionary of temporal features
        """
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return {
                "hour_of_day": dt.hour,
                "day_of_week": dt.weekday(),  # Monday=0, Sunday=6
                "day_of_month": dt.day,
                "month": dt.month,
                "is_weekend": dt.weekday() >= 5,  # Saturday or Sunday
            }
        except (ValueError, AttributeError):
            # Return defaults if parsing fails
            return {
                "hour_of_day": 12,
                "day_of_week": 0,
                "day_of_month": 15,
                "month": 1,
                "is_weekend": False,
            }

    def process_amount(self, amount: float) -> Dict[str, Any]:
        """
        Process transaction amount into features.

        Args:
            amount: Transaction amount

        Returns:
            Dictionary of amount-based features
        """
        import math

        # Log transformation to handle right-skewed distribution
        log_amount = math.log(max(amount, 0.001))  # Avoid log(0)

        # Amount binning
        if amount < 50:
            amount_bin = "low"
        elif amount < 500:
            amount_bin = "medium"
        else:
            amount_bin = "high"

        return {
            "amount": amount,
            "log_amount": log_amount,
            "amount_bin": amount_bin,
            "is_high_value": amount >= 1000,
            "is_very_high_value": amount >= 5000,
        }

    def create_feature_vector(
        self, transaction: Dict[str, Any]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Create complete feature vector with metadata.

        Args:
            transaction: Transaction data

        Returns:
            Tuple of (feature_vector, feature_metadata)
        """
        # Basic features (Time, Amount, V1-V28 placeholders)
        basic_features = self.process_transaction(transaction)

        # Additional engineered features
        temporal_features = self.extract_temporal_features(
            transaction.get("timestamp", "")
        )
        amount_features = self.process_amount(float(transaction.get("amount", 0.0)))

        # Combine all features for metadata
        feature_metadata = {
            "temporal": temporal_features,
            "amount": amount_features,
            "raw_transaction_id": transaction.get("transactionId"),
        }

        return basic_features, feature_metadata