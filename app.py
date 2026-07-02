"""
ShopMate AI - Main FastAPI Application Entry Point
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routes.recommend import router as recommend_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("shopmate-ai")

# Initialize FastAPI app
app = FastAPI(
    title="ShopMate AI",
    description="Intelligent Retail Recommendation System powered by Gemini + Firecrawl",
    version="1.0.0"
)

# Allow all origins for development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(recommend_router, prefix="/api", tags=["Recommendations"])

@app.get("/api/info")
async def info():
    return {
        "message": "Welcome to ShopMate AI API",
        "version": "1.0.0",
        "endpoints": {
            "recommend": "POST /api/recommend",
            "get_memory": "GET /api/memory/{user_id}",
            "update_memory": "POST /api/memory/update"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Mount static UI at root
app.mount("/", StaticFiles(directory="static", html=True), name="static")
