#!/usr/bin/env python3
"""
Transaction Generator for Fraud Detection Platform
"""

import os
import time
import logging
from faker import Faker
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fake = Faker()

def generate_transaction():
    """Generate a random transaction"""
    return {
        "customerId": fake.uuid4(),
        "cardId": fake.uuid4(),
        "amount": round(fake.random_number(digits=5) / 100, 2),
        "currency": fake.random_element(["USD", "EUR", "GBP", "JPY", "CAD"]),
        "merchant": fake.company(),
        "merchantCategory": fake.random_element(["retail", "food", "travel", "entertainment", "utilities"]),
        "location": fake.city(),
        "latitude": float(fake.latitude()),
        "longitude": float(fake.longitude()),
        "timestamp": fake.iso8601()
    }

def main():
    """Main function to generate transactions"""
    transaction_service_url = os.getenv("TRANSACTION_SERVICE_URL", "http://localhost:8080/api/v1/transactions")
    generation_rate = int(os.getenv("GENERATION_RATE", "10"))  # transactions per second

    logger.info(f"Starting transaction generator targeting {transaction_service_url}")
    logger.info(f"Generation rate: {generation_rate} transactions/second")

    while True:
        try:
            transaction = generate_transaction()
            # In a real implementation, we would send this to the transaction service
            # For now, just log it
            logger.info(f"Generated transaction: {transaction['transactionId'] if 'transactionId' in transaction else 'N/A'}")
            time.sleep(1.0 / generation_rate)
        except Exception as e:
            logger.error(f"Error generating transaction: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()