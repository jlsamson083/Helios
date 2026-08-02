from fastapi import FastAPI

app = FastAPI(
    title="Helios API",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "message": "Welcome to Helios ☀️"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "project": "Helios",
        "version": "0.1.0"
    }