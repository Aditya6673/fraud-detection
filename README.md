# Real-Time Fraud Detection Platform

This is a production-ready real-time fraud detection platform built with microservices architecture.

## Architecture

The platform consists of four main services:
- Transaction Service (Java/Spring Boot)
- Fraud Detection Service (Python/FastAPI)
- Analytics Service (Java/Spring Boot)
- Transaction Generator (Python)

And supporting components:
- PostgreSQL (primary database)
- Kafka (event streaming)
- Redis (feature store)

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Java 21 (for building services)
- Python 3.11+ (for ML service and generator)

### Quick Start

1. Clone the repository
2. Build and start all services:
   ```bash
   docker-compose up --build
   ```

3. The services will be available at:
   - Transaction Service: http://localhost:8080
   - Fraud Detection Service: http://localhost:8000
   - Analytics Service: http://localhost:8081
   - API Documentation:
     - Transaction Service: http://localhost:8080/swagger-ui.html
     - Fraud Detection Service: http://localhost:8000/docs
     - Analytics Service: http://localhost:8081/swagger-ui.html

## Development

Each service can be developed independently. Refer to each service's directory for specific build and run instructions.
