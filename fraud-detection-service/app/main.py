from fastapi import FastAPI

app = FraudDetectionService()
app.title = "Fraud Detection Service"
app.description = "Service for scoring transactions for fraud risk"
app.version = "0.0.1"


@app.get("/")
async def root():
    return {"message": "Fraud Detection Service is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)