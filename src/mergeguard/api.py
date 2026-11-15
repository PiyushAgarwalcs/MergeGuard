# mergeguard.api
# Exposes the FastAPI application and health endpoint for the review service.

from fastapi import FastAPI

app = FastAPI(title="MergeGuard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
