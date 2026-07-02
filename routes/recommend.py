"""
ShopMate AI - API Routes
Handles /recommend, /memory GET, and /memory/update endpoints
"""

import logging
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.memory import MemoryService
from services.crawler import CrawlerService
from services.llm import LLMService
from services.processor import ProcessorService

logger = logging.getLogger("shopmate-ai.routes")

router = APIRouter()

# Initialize services
memory_service = MemoryService()
crawler_service = CrawlerService()
llm_service = LLMService()
processor_service = ProcessorService()


def _build_fallback_recommendations(products: list[dict], limit: int = 3) -> str:
    lines = ["Recommended Products:"]
    for index, product in enumerate(products[:limit], 1):
        name = product.get("name") or "Product"
        price = f"₹{product['price']:.0f}" if product.get("price") else "N/A"
        rating = f"{product['rating']:.1f}/5" if product.get("rating") else "N/A"
        source = product.get("source") or "shopping result"
        url = product.get("url") or product.get("product_url") or ""
        lines.extend([
            "",
            f"{index}. {name}",
            f"   - Price: {price}",
            f"   - Rating: {rating}",
            f"   - Available at: {source}",
            f"   - Link: {url or 'N/A'}",
        ])
    return "\n".join(lines)


def _is_incomplete_recommendation(text: str) -> bool:
    if not text or len(text.strip()) < 120:
        return True
    required_parts = ["Recommended Products", "Price", "Rating", "Available at", "Link"]
    if any(part not in text for part in required_parts):
        return True
    return len(re.findall(r'^\s*\d+\.', text, re.MULTILINE)) < 2


# --------------------
# Request / Response Models
# --------------------

class RecommendRequest(BaseModel):
    user_id: str
    query: str

class MemoryUpdateRequest(BaseModel):
    user_id: str
    category: Optional[str] = None
    budget: Optional[float] = None


# --------------------
# POST /recommend
# --------------------

@router.post("/recommend")
async def recommend(request: RecommendRequest):
    """
    Main recommendation endpoint.
    Flow: Memory → Firecrawl → Gemini LLM → Response
    """
    user_id = request.user_id.strip()
    query = request.query.strip()

    if not user_id or not query:
        raise HTTPException(status_code=400, detail="user_id and query are required.")

    logger.info(f"[{user_id}] Received query: {query}")

    try:
        # Step 1: Update memory with new query
        memory = memory_service.update_memory(user_id, query)
        logger.info(f"[{user_id}] Memory updated: {memory}")

        # Step 2: Scrape trending products via Firecrawl
        products = await crawler_service.scrape_products(query)
        logger.info(f"[{user_id}] Scraped {len(products)} products")

        if not products:
            raise HTTPException(
                status_code=503,
                detail="Could not retrieve product data. Try again later."
            )

        # Step 3: Process/rank products before sending to LLM
        ranked_products = processor_service.rank_products(products, memory)
        logger.info(f"[{user_id}] Ranked {len(ranked_products)} products")

        # Step 4: Generate recommendations via Gemini
        try:
            recommendations = await llm_service.generate_recommendations(
                user_query=query,
                user_memory=memory,
                products=ranked_products
            )
        except Exception as e:
            logger.warning(f"[{user_id}] LLM unavailable. Using fallback recommendations: {e}")
            recommendations = _build_fallback_recommendations(ranked_products)

        if _is_incomplete_recommendation(recommendations):
            logger.warning(f"[{user_id}] LLM response was incomplete. Using fallback recommendations.")
            recommendations = _build_fallback_recommendations(ranked_products)

        logger.info(f"[{user_id}] Recommendations generated")

        return {
            "user_id": user_id,
            "query": query,
            "memory_snapshot": memory,
            "recommendations": recommendations,
            "products_analyzed": len(products)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{user_id}] Error during recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# --------------------
# GET /memory/{user_id}
# --------------------

@router.get("/memory/{user_id}")
async def get_memory(user_id: str):
    """
    Retrieve stored memory/profile for a given user.
    """
    memory = memory_service.get_memory(user_id)
    if not memory:
        raise HTTPException(status_code=404, detail=f"No memory found for user '{user_id}'.")
    return {"user_id": user_id, "memory": memory}


# --------------------
# POST /memory/update
# --------------------

@router.post("/memory/update")
async def update_memory(request: MemoryUpdateRequest):
    """
    Manually update category or budget for a user.
    """
    user_id = request.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")

    updated = memory_service.manual_update(
        user_id=user_id,
        category=request.category,
        budget=request.budget
    )
    return {"user_id": user_id, "updated_memory": updated}
