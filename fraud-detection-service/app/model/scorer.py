"""
Scoring engine components for fraud detection service.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class FraudScoringEngine:
    """
    Main scoring engine that applies ML model to generate fraud risk scores.
    """

    def __init__(
        self,
        model_loader: Any,
        feature_processor: Any,
        risk_threshold_low: float = 30.0,
        risk_threshold_high: float = 70.0,
    ):
        """
        Initialize the scoring engine.

        Args:
            model_loader: Instance of FraudDetectionModel
            feature_processor: Instance of TransactionFeatureProcessor
            risk_threshold_low: Score below which transaction is APPROVED
            risk_threshold_high: Score above which transaction is BLOCKED
        """
        self.model_loader = model_loader
        self.feature_processor = feature_processor
        self.risk_threshold_low = risk_threshold_low
        self.risk_threshold_high = risk_threshold_high
        self.logger = logging.getLogger(__name__ + ".FraudScoringEngine")

    def score_transaction(
        self, transaction: Dict[str, Any]
    ) -> Tuple[float, str, List[str], Optional[float]]:
        """
        Score a transaction for fraud risk.

        Args:
            transaction: Transaction data matching ScoreRequest format

        Returns:
            Tuple of (risk_score, risk_level, reasons, anomaly_score)
        """
        try:
            # Extract features
            features, feature_metadata = self.feature_processor.create_feature_vector(
                transaction
            )

            # Get risk score from ML model if available
            if self.model_loader.is_available():
                risk_score_raw = self.model_loader.predict(features)
                risk_score = float(risk_score_raw[0])  # Extract scalar from array
                self.logger.debug(
                    f"ML model prediction: {risk_score_raw} -> {risk_score}"
                )
            else:
                # Fallback to rule-based scoring
                risk_score = self._rule_based_scoring(transaction, feature_metadata)
                self.logger.warning(
                    f"Using rule-based scoring (ML unavailable): {risk_score}"
                )

            # Ensure score is in valid range
            risk_score = max(0.0, min(100.0, risk_score))

            # Determine risk level
            risk_level = self._get_risk_level(risk_score)

            # Generate explanation reasons
            reasons = self._generate_reasons(
                transaction, risk_score, feature_metadata
            )

            # Calculate anomaly score (optional)
            anomaly_score = self._calculate_anomaly_score(features)

            return risk_score, risk_level, reasons, anomaly_score

        except Exception as e:
            self.logger.error(f"Scoring failed: {e}")
            # Return safe defaults
            return 50.0, "REVIEW", ["Scoring error occurred"], None

    def _rule_based_scoring(
        self, transaction: Dict[str, Any], feature_metadata: Dict[str, Any]
    ) -> float:
        """
        Apply rule-based scoring when ML model is unavailable.

        Args:
            transaction: Transaction data
            feature_metadata: Engineered features

        Returns:
            Risk score (0-100)
        """
        score = 0.0
        amount = float(transaction.get("amount", 0.0))

        # Amount-based rules
        if amount >= 10000:
            score += 40
        elif amount >= 5000:
            score += 30
        elif amount >= 1000:
            score += 20
        elif amount >= 500:
            score += 10

        # Time-based rules (unusual hours)
        hour = feature_metadata.get("temporal", {}).get("hour_of_day", 12)
        if hour < 6 or hour > 22:  # Outside 6 AM - 10 PM
            score += 15

        # Weekend transactions might be slightly riskier
        if feature_metadata.get("temporal", {}).get("is_weekend", False):
            score += 10

        # Ensure score is in reasonable range
        return min(95.0, max(5.0, score))  # Keep between 5-95 for rule-based

    def _get_risk_level(self, risk_score: float) -> str:
        """
        Convert risk score to risk level.

        Args:
            risk_score: Score between 0 and 100

        Returns:
            Risk level: "APPROVED", "REVIEW", or "BLOCKED"
        """
        if risk_score < self.risk_threshold_low:
            return "APPROVED"
        elif risk_score > self.risk_threshold_high:
            return "BLOCKED"
        else:
            return "REVIEW"

    def _generate_reasons(
        self,
        transaction: Dict[str, Any],
        risk_score: float,
        feature_metadata: Dict[str, Any],
    ) -> List[str]:
        """
        Generate human-readable explanations for the risk score.

        Args:
            transaction: Transaction data
            risk_score: Calculated risk score
            feature_metadata: Engineered features

        Returns:
            List of reason strings
        """
        reasons = []
        amount = float(transaction.get("amount", 0.0))

        # Amount-based reasons
        if amount >= 10000:
            reasons.append(
                f"Very high transaction amount: ${amount:,.2f}"
            )
        elif amount >= 5000:
            reasons.append(
                f"High transaction amount: ${amount:,.2f}"
            )
        elif amount >= 1000:
            reasons.append(
                f"Moderate-high transaction amount: ${amount:,.2f}"
            )

        # Time-based reasons
        hour = feature_metadata.get("temporal", {}).get("hour_of_day", 12)
        if hour < 6 or hour > 22:
            reasons.append(
                f"Transaction outside normal hours: {hour:02d}:00"
            )

        # Weekend reason
        if feature_metadata.get("temporal", {}).get("is_weekend", False):
            reasons.append("Weekend transaction")

        # High-value indicators
        if feature_metadata.get("amount", {}).get("is_high_value", False):
            reasons.append("High-value transaction (>$1,000)")

        if feature_metadata.get("amount", {}).get("is_very_high_value", False):
            reasons.append("Very high-value transaction (>$5,000)")

        # If no specific reasons found, give general ones
        if not reasons:
            if risk_score >= 70:
                reasons.append("Multiple risk factors detected")
            elif risk_score >= 30:
                reasons.append("Some risk factors present")
            else:
                reasons.append("Normal transaction pattern")

        # Limit to top 3-5 reasons as suggested in plan
        return reasons[:5]

    def _calculate_anomaly_score(self, features: np.ndarray) -> Optional[float]:
        """
        Calculate anomaly score using isolation forest or similar.
        This is optional and would require a separate anomaly detection model.

        Args:
            features: Feature vector

        Returns:
            Anomaly score or None if not implemented
        """
        # Placeholder for anomaly detection
        # In a full implementation, this would use a separate model
        # like Isolation Forest to detect anomalous transactions
        return None

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        if not self.model_loader.is_available():
            return {"available": False}

        return {
            "available": True,
            "version": self.model_loader.get_version(),
            "metadata": getattr(self.model_loader, "metadata", {}),
        }