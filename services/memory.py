"""
ShopMate AI - Memento-Style Memory Service
Tracks user behavior, preferences, and history across sessions.
Persists data to data/users.json (lightweight file-based storage).
"""

import json
import os
import re
import logging
from typing import Optional

logger = logging.getLogger("shopmate-ai.memory")

# Path to the persistent user memory store
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")

# Category keyword mapping for preference extraction
CATEGORY_KEYWORDS = {
    "electronics": ["phone", "laptop", "tablet", "headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "speaker",
                    "camera", "tv", "television", "monitor", "keyboard", "mouse",
                    "smartwatch", "watch", "gaming", "console", "charger", "router"],
    "fashion": ["shirt", "jeans", "dress", "shoes", "sneakers", "jacket", "hoodie",
                "bag", "handbag", "sunglasses", "watch", "cap", "hat", "boots",
                "sandals", "kurta", "saree", "leggings", "skirt", "blazer"],
    "home": ["sofa", "chair", "table", "bed", "mattress", "pillow", "lamp",
             "curtain", "shelf", "storage", "kitchen", "cookware", "blender",
             "fan", "ac", "air conditioner", "refrigerator", "washing machine"],
    "beauty": ["lipstick", "foundation", "moisturizer", "serum", "shampoo",
               "conditioner", "perfume", "face wash", "sunscreen", "mascara",
               "eyeliner", "blush", "skincare", "haircare"],
    "sports": ["cricket", "football", "yoga", "gym", "dumbbell", "treadmill",
               "cycle", "bicycle", "badminton", "tennis", "running", "fitness",
               "protein", "supplement", "mat"],
    "books": ["book", "novel", "textbook", "fiction", "non-fiction", "kindle",
              "ebook", "biography", "comic", "manga"],
    "grocery": ["food", "snack", "organic", "fruit", "vegetable", "milk",
                "coffee", "tea", "chocolate", "biscuit", "dry fruit", "oil"],
}


class MemoryService:
    """
    Implements a Memento-style memory system for ShopMate AI.
    Each user has a persistent profile with:
      - history: list of past queries
      - category: inferred product category
      - budget: extracted numeric budget
    """

    def __init__(self):
        self._ensure_data_file()

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def _ensure_data_file(self):
        """Make sure the data directory and users.json file exist."""
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump({}, f)
            logger.info("Created new users.json data file.")

    def _load_all(self) -> dict:
        """Load all user memories from disk."""
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load memory file: {e}")
            return {}

    def _save_all(self, data: dict):
        """Persist all user memories to disk."""
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save memory file: {e}")

    def _default_memory(self) -> dict:
        """Return an empty Memento-style memory template."""
        return {
            "history": [],
            "category": "",
            "budget": None
        }

    # ---------------------------
    # Preference extraction
    # ---------------------------

    def _extract_category(self, query: str) -> str:
        """
        Scan query for category keywords.
        Returns the best-matching category or empty string.
        """
        query_lower = query.lower()
        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[category] = score
        if scores:
            return max(scores, key=scores.get)
        return ""

    def _extract_budget(self, query: str) -> Optional[float]:
        """
        Extract numeric budget from query text.
        Handles patterns like:
          - "under 5000", "below 10k", "less than 2000"
          - "budget of 3000", "within ₹500", "upto 800"
          - bare numbers like "5000 rupees"
        """
        query_lower = query.lower()

        # Replace shorthand 'k' with '000' (e.g., 5k → 5000)
        query_lower = re.sub(r'(\d+)\s*k\b', lambda m: str(int(m.group(1)) * 1000), query_lower)

        # Patterns that indicate a budget ceiling
        patterns = [
            r'(?:under|below|less than|within|upto|up to|max|maximum|budget of|around|approximately|₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:rupees|rs|inr|₹)',
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        return None

    # ---------------------------
    # Public API
    # ---------------------------

    def get_memory(self, user_id: str) -> Optional[dict]:
        """Retrieve memory for a given user_id. Returns None if not found."""
        all_data = self._load_all()
        return all_data.get(user_id)

    def update_memory(self, user_id: str, query: str) -> dict:
        """
        Append query to history and update category/budget.
        This is the core Memento step — called on every /recommend request.
        """
        all_data = self._load_all()

        # Initialize memory if user is new
        if user_id not in all_data:
            all_data[user_id] = self._default_memory()
            logger.info(f"New user detected: {user_id}")

        memory = all_data[user_id]

        # --- Memento: append query to history ---
        memory["history"].append(query)

        # Keep history bounded to last 20 queries (sliding window)
        if len(memory["history"]) > 20:
            memory["history"] = memory["history"][-20:]

        # --- Extract and update category ---
        new_category = self._extract_category(query)
        if new_category:
            memory["category"] = new_category

        # --- Extract and update budget ---
        new_budget = self._extract_budget(query)
        if new_budget is not None:
            memory["budget"] = new_budget

        all_data[user_id] = memory
        self._save_all(all_data)

        logger.debug(f"[{user_id}] Memory: {memory}")
        return memory

    def manual_update(self, user_id: str, category: Optional[str], budget: Optional[float]) -> dict:
        """
        Manually override category and/or budget for a user.
        Used by POST /memory/update.
        """
        all_data = self._load_all()

        if user_id not in all_data:
            all_data[user_id] = self._default_memory()

        if category:
            all_data[user_id]["category"] = category
        if budget is not None:
            all_data[user_id]["budget"] = budget

        self._save_all(all_data)
        return all_data[user_id]
