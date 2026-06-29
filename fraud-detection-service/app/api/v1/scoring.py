"""
Scoring API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from ...model.scorer import FraudScoringEngine

router = APIRouter()


def get_scoring_engine() -> FraudScoringEngine:
    """Dependency to get scoring engine instance."""
    # This would be imported from main.py in a real implementation
    # For now, we'll create a placeholder that would be replaced
    # by the actual dependency injection
    from ...main import scoring_engine

    if scoring_engine is None:
        raise HTTPException(
            status_code=503, detail="Scoring engine not initialized"
        )
    return scoring_engine


@router.post("/", response_model=Dict[str, Any])
async def score_transaction(
    transaction: Dict[str, Any],
    engine: FraudScoringEngine = Depends(get_scoring_engine),
) -> Dict[str, Any]:
    """
    Score a transaction for fraud risk.

    Args:
        transaction: Transaction data matching ScoreRequest format

    Returns:
        Scoring result matching ScoreResponse format
    """
    try:
        # Score the transaction
        risk_score, risk_level, reasons, anomaly_score = engine.score_transaction(
            transaction
        )

        # Prepare response matching ScoreResponse schema
        response = {
            "transactionId": transaction.get("transactionId"),
            "riskScore": round(risk_score, 2),
            "status": risk_level,
            "reasons": reasons,
            "modelVersion": engine.get_model_info().get("version", "unknown"),
            "mlAvailable": engine.get_model_info().get("available", False),
            "timestamp": (
                transaction.get("timestamp")
                if transaction.get("timestamp")
                else None
            ),  # Use transaction timestamp or current time
        }

        # Add optional fields if present
        if anomaly_score is not None:
            response["anomalyScore"] = round(anomaly_score, 2)

        return response

    except Exception as e:
        logger.error(f"Error scoring transaction: {e}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


# Import logger
import logging

logger = logging.getLogger(__name__)