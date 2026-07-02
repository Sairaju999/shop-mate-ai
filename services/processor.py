"""
ShopMate AI - Product Processor Service
Ranks and filters scraped products based on user memory
before sending to the LLM for final recommendation.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("shopmate-ai.processor")


class ProcessorService:
    """
    Pre-processes and ranks products using:
    - User budget (from Memento memory)
    - Rating scores
    - Category preference alignment
    
    This reduces noise before sending data to Gemini.
    """

    def _filter_by_budget(
        self,
        products: List[Dict],
        budget: Optional[float]
    ) -> List[Dict]:
        """
        Filter out products exceeding user's budget.
        If no budget is set, return all products.
        Add a 10% buffer to budget (e.g., ₹5000 budget → allow up to ₹5500).
        """
        if not budget:
            return products

        buffer = budget * 1.10  # 10% flexibility
        filtered = [p for p in products if p.get("price") is not None and p["price"] <= buffer]

        logger.info(
            f"Budget filter: {len(products)} → {len(filtered)} products "
            f"(budget ₹{budget}, buffer ₹{buffer:.0f})"
        )
        return filtered

    def _score_product(self, product: Dict, memory: Dict) -> float:
        """
        Compute a ranking score for a product.

        Score = (rating * 2) + budget_bonus
        
        - Rating contributes most to score (out of 10)
        - Budget bonus: cheaper products within budget score higher
        """
        score = 0.0

        # Rating component (0–10)
        rating = product.get("rating") or 0.0
        score += rating * 2.0

        # Budget proximity bonus: closer to budget ceiling = higher bonus
        budget = memory.get("budget")
        price = product.get("price")
        if budget and price and price <= budget:
            # Relative value: score increases as price drops vs budget
            proximity = (budget - price) / budget  # 0 to 1
            score += proximity * 2.0  # adds up to 2 bonus points

        return round(score, 3)

    def rank_products(
        self,
        products: List[Dict[str, Any]],
        memory: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Main ranking pipeline:
        1. Filter by budget
        2. Score each product
        3. Sort by score descending
        4. Return top 10 for LLM
        """
        if not products:
            return []

        # Step 1: Apply budget filter
        budget = memory.get("budget")
        filtered = self._filter_by_budget(products, budget)

        # If budget filter removes everything, fall back to all products
        if not filtered:
            logger.warning("Budget filter removed all products. Using unfiltered set.")
            filtered = products

        # Step 2: Score each product
        for product in filtered:
            product["_score"] = self._score_product(product, memory)

        # Step 3: Sort by score descending
        ranked = sorted(filtered, key=lambda p: p["_score"], reverse=True)

        # Step 4: Return top 10 (LLM will pick final 3–5)
        top = ranked[:10]

        logger.info(f"Ranked products (top {len(top)}):")
        for i, p in enumerate(top, 1):
            logger.debug(
                f"  {i}. {p['name'][:50]} | ₹{p.get('price')} | "
                f"★{p.get('rating')} | score={p['_score']}"
            )

        return top

    def format_for_prompt(self, products: List[Dict]) -> str:
        """
        Format ranked product list into a clean string for the LLM prompt.
        """
        if not products:
            return "No products available."

        lines = []
        for i, p in enumerate(products, 1):
            name = p.get("name", "Unknown")
            price = f"₹{p['price']:.0f}" if p.get("price") else "N/A"
            rating = f"{p['rating']:.1f}/5" if p.get("rating") else "N/A"
            source = p.get("source") or "shopping result"
            url = p.get("url") or p.get("product_url") or "N/A"
            lines.append(
                f"{i}. {name}\n"
                f"   Price: {price} | Rating: {rating} | Available at: {source} | Link: {url}"
            )

        return "\n".join(lines)
