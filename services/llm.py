"""
ShopMate AI - LLM Service (Google Gemini)
Generates personalized product recommendations using
user memory + scraped product data.
"""

import os
import logging
import asyncio
from typing import List, Dict, Any

import google.generativeai as genai
from dotenv import load_dotenv

from services.processor import ProcessorService

load_dotenv()
logger = logging.getLogger("shopmate-ai.llm")

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set. LLM calls will fail.")

processor_service = ProcessorService()


class LLMService:
    """
    Wraps the Gemini API to generate structured product recommendations.
    Uses the ShopMate AI prompt template.
    """

    def __init__(self):
        self.model_name = "gemini-2.5-flash"  # Fast and cost-effective
        try:
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini model initialized: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None

    def _build_prompt(
        self,
        user_query: str,
        user_memory: Dict[str, Any],
        products: List[Dict[str, Any]]
    ) -> str:
        """
        Build the full ShopMate AI prompt for Gemini.
        Injects: user query, memory snapshot, and product list.
        """
        # Format memory for readability
        history_str = (
            ", ".join(user_memory.get("history", [])[-5:])  # Last 5 queries
            or "No history yet"
        )
        category_str = user_memory.get("category") or "Not determined"
        budget_val = user_memory.get("budget")
        budget_str = f"₹{budget_val:.0f}" if budget_val else "Not specified"

        memory_block = (
            f"- Recent Queries: {history_str}\n"
            f"- Preferred Category: {category_str}\n"
            f"- Budget: {budget_str}"
        )

        # Format product list
        products_block = processor_service.format_for_prompt(products)

        prompt = f"""You are ShopMate AI, an intelligent retail recommendation assistant.

Your goal is to generate personalized product recommendations using:
- Real-time product trends (Firecrawl data)
- User memory (Memento-style)

----------------------------------------
USER QUERY:
{user_query}

USER MEMORY:
{memory_block}

TRENDING PRODUCTS:
{products_block}

----------------------------------------

INSTRUCTIONS:

- Analyze user memory:
    history, category, budget

- Analyze product data:
    ratings, price, popularity

- Combine both:
    prioritize products matching user preferences and trends

- Recommend ONLY top 2-3 products

For each product include:
- Name
- Price
- Rating
- Available at
- Link

----------------------------------------

RULES:

- Do NOT hallucinate products
- Use ONLY the products provided in TRENDING PRODUCTS above
- Include the product link exactly as provided
- Respect user budget strictly — exclude products above budget if budget is set
- Prefer personalized matches over general popularity
- If fewer than 3 products match, recommend what is available with honest explanation

----------------------------------------

OUTPUT FORMAT:

Recommended Products:

1. Product Name
   - Price:
   - Rating:
   - Available at:
   - Link:

2. Product Name
   - Price:
   - Rating:
   - Available at:
   - Link:

(continue for all recommended products)

----------------------------------------

Generate final recommendations now.
"""
        return prompt

    async def generate_recommendations(
        self,
        user_query: str,
        user_memory: Dict[str, Any],
        products: List[Dict[str, Any]]
    ) -> str:
        """
        Call Gemini API with the full ShopMate prompt.
        Returns the raw recommendation text.
        """
        if not self.model:
            raise RuntimeError("Gemini model is not initialized. Check GEMINI_API_KEY.")

        if not products:
            return "No products were found to recommend. Please try a different search query."

        prompt = self._build_prompt(user_query, user_memory, products)
        logger.debug(f"Sending prompt to Gemini ({len(prompt)} chars)")

        try:
            generation_config = genai.GenerationConfig(
                temperature=0.4,      # Slightly creative but mostly factual
                max_output_tokens=1024,
                top_p=0.9,
            )
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=generation_config,
                ),
                timeout=8.0,
            )

            result = response.text.strip()
            logger.info("Gemini response received successfully")
            return result

        except asyncio.TimeoutError:
            logger.warning("Gemini API timed out.")
            raise RuntimeError("LLM generation timed out")
        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise RuntimeError(f"LLM generation failed: {str(e)}")
