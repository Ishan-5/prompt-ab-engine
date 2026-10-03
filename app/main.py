"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from app.api import experiments

app = FastAPI(title="Prompt A/B Testing Engine")

app.include_router(experiments.router)


@app.get("/")
def health_check():
    return {"status": "ok"}