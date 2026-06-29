"""
Kafka consumer service for processing transaction events.
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from confluent_kafka import Consumer, KafkaError, KafkaException

from ..model.config import settings
from ..model.scorer import FraudScoringEngine

logger = logging.getLogger(__name__)


class KafkaTransactionConsumer:
    """
    Consumes transaction events from Kafka and processes them for fraud scoring.
    """

    def __init__(
        self,
        scoring_engine: FraudScoringEngine,
        message_handler: Optional[Callable] = None,
    ):
        """
        Initialize the Kafka consumer.

        Args:
            scoring_engine: Engine to score transactions
            message_handler: Optional custom handler for processed messages
        """
        self.scoring_engine = scoring_engine
        self.custom_handler = message_handler
        self.consumer: Optional[Consumer] = None
        self.running = False
        self.consumer_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(__name__ + ".KafkaTransactionConsumer")

        # Consumer configuration
        self.conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_CONSUMER_GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # Manual commit for control
        }

    def start(self) -> None:
        """Start the Kafka consumer in a background thread."""
        if self.running:
            self.logger.warning("Consumer is already running")
            return

        try:
            self.consumer = Consumer(self.conf)
            self.consumer.subscribe([settings.KAFKA_TRANSACTIONS_TOPIC])
            self.running = True

            self.consumer_thread = threading.Thread(
                target=self._consume_loop, daemon=True
            )
            self.consumer_thread.start()
            self.logger.info(
                f"Started Kafka consumer for topic {settings.KAFKA_TRANSACTIONS_TOPIC}"
            )

        except Exception as e:
            self.logger.error(f"Failed to start Kafka consumer: {e}")
            self.running = False
            raise

    def stop(self) -> None:
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5.0)
        if self.consumer:
            self.consumer.close()
        self.logger.info("Stopped Kafka consumer")

    def _consume_loop(self) -> None:
        """Main consumer loop."""
        self.logger.info("Kafka consumer loop started")

        while self.running:
            try:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event
                        self.logger.debug(
                            f"End of partition reached {msg.topic()} [{msg.partition()}]"
                        )
                    elif msg.error():
                        self.logger.error(f"Kafka error: {msg.error()}")
                    continue

                # Process the message
                self._process_message(msg)

            except KafkaException as e:
                self.logger.error(f"Kafka exception in consumer loop: {e}")
                time.sleep(1)  # Brief pause before retrying
            except Exception as e:
                self.logger.error(f"Unexpected error in consumer loop: {e}")
                time.sleep(1)

        self.logger.info("Kafka consumer loop stopped")

    def _process_message(self, msg) -> None:
        """
        Process a single Kafka message.

        Args:
            msg: Kafka message object
        """
        try:
            # Deserialize message value
            value = msg.value().decode("utf-8")
            transaction_data = json.loads(value)

            self.logger.debug(
                f"Received transaction {transaction_data.get('transactionId')}"
            )

            # Score the transaction
            risk_score, risk_level, reasons, anomaly_score = (
                self.scoring_engine.score_transaction(transaction_data)
            )

            # Prepare result
            result = {
                "transactionId": transaction_data.get("transactionId"),
                "riskScore": risk_score,
                "riskLevel": risk_level,
                "reasons": reasons,
                "anomalyScore": anomaly_score,
                "modelVersion": self.scoring_engine.get_model_info().get("version"),
                "mlAvailable": self.scoring_engine.get_model_info().get(
                    "available", False
                ),
                "timestamp": datetime.now().isoformat(),
                "originalTransaction": transaction_data,
            }

            # Handle the result
            if self.custom_handler:
                self.custom_handler(result)
            else:
                self._default_handler(result, msg)

            # Commit offset
            self.consumer.commit(msg)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON message: {e}")
            # Still commit to avoid reprocessing bad message
            self.consumer.commit(msg)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            # Don't commit on processing error - message will be retried
            # In production, you might want to send to dead letter queue after retries

    def _default_handler(
        self, result: Dict[str, Any], msg
    ) -> None:
        """
        Default handler for processed transactions.

        Args:
            result: Scoring result
            msg: Original Kafka message
        """
        # Log the result
        self.logger.info(
            f"Scored transaction {result['transactionId']}: "
            f"risk={result['riskScore']:.1f}, "
            f"level={result['riskLevel']}, "
            f"ml_available={result['mlAvailable']}"
        )

        # In a full implementation, you might:
        # 1. Publish results to a "fraud-scores" topic
        # 2. Store results in a database
        # 3. Trigger alerts for high-risk transactions
        # 4. Update caches

        # For now, we just log
        if result["riskLevel"] == "BLOCKED":
            self.logger.warning(
                f"HIGH RISK TRANSACTION: {result['transactionId']} "
                f"score={result['riskScore']:.1f}"
            )

    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the Kafka consumer.

        Returns:
            Dictionary with health status
        """
        return {
            "running": self.running,
            "consumer_connected": self.consumer is not None,
            "subscribed_topic": settings.KAFKA_TRANSACTIONS_TOPIC,
            "consumer_group": settings.KAFKA_CONSUMER_GROUP_ID,
        }


# Helper function to create a consumer instance
def create_transaction_consumer(
    scoring_engine: FraudScoringEngine,
) -> KafkaTransactionConsumer:
    """
    Factory function to create a Kafka transaction consumer.

    Args:
        scoring_engine: Engine to score transactions

    Returns:
        Configured KafkaTransactionConsumer instance
    """
    return KafkaTransactionConsumer(scoring_engine)