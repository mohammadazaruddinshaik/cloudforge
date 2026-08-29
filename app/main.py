from fastapi import FastAPI

from app.api.routes.repositories import router as repositories_router

app = FastAPI(title="CloudForge")
app.include_router(repositories_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
