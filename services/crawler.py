"""
ShopMate AI - Trend Scraping Service (Firecrawl)
Dynamically generates search URLs and scrapes product data
(name, price, rating) from e-commerce sites.
"""

import os
import re
import logging
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("shopmate-ai.crawler")

FIRECRAWL_API_KEY = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
SEARCH_SOURCES = {
    "amazon.in": "https://www.amazon.in/s?k={query}",
    "flipkart.com": "https://www.flipkart.com/search?q={query}",
}

# Fallback cache to avoid re-scraping the same query in a short window
_scrape_cache: Dict[str, List[Dict]] = {}

FALLBACK_PRODUCTS: Dict[str, List[Dict[str, Any]]] = {
    "electronics": [
        {"name": "Samsung Galaxy M35 5G", "price": 16999.0, "rating": 4.1, "source": "local fallback"},
        {"name": "realme Narzo 70 Pro 5G", "price": 15999.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Redmi Note 13 Pro", "price": 18999.0, "rating": 4.2, "source": "local fallback"},
        {"name": "OnePlus Nord Buds 2r", "price": 1799.0, "rating": 4.2, "source": "local fallback"},
        {"name": "boAt Airdopes 141 Bluetooth Earbuds", "price": 1299.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Boult Z40 Pro Wireless Earbuds", "price": 1499.0, "rating": 4.1, "source": "local fallback"},
        {"name": "HP 15s Ryzen 5 Laptop", "price": 42990.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Lenovo IdeaPad Slim 3 Laptop", "price": 37990.0, "rating": 4.1, "source": "local fallback"},
        {"name": "LG 1.5 Ton 5 Star Dual Inverter AC", "price": 41990.0, "rating": 4.2, "source": "local fallback"},
        {"name": "Acer 109 cm 4K Ultra HD Smart TV", "price": 29999.0, "rating": 4.0, "source": "local fallback"},
    ],
    "electronics_phone": [
        {"name": "Samsung Galaxy M35 5G", "price": 16999.0, "rating": 4.1, "source": "local fallback"},
        {"name": "realme Narzo 70 Pro 5G", "price": 15999.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Redmi Note 13 Pro", "price": 18999.0, "rating": 4.2, "source": "local fallback"},
        {"name": "POCO X6 Pro 5G", "price": 17999.0, "rating": 4.1, "source": "local fallback"},
        {"name": "iQOO Z9x 5G", "price": 17990.0, "rating": 4.1, "source": "local fallback"},
    ],
    "electronics_audio": [
        {"name": "boAt Airdopes 141 Bluetooth Earbuds", "price": 1299.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Boult Z40 Pro Wireless Earbuds", "price": 1499.0, "rating": 4.1, "source": "local fallback"},
        {"name": "OnePlus Nord Buds 2r", "price": 1799.0, "rating": 4.2, "source": "local fallback"},
        {"name": "Sony WH-CH720N Headphones", "price": 4999.0, "rating": 4.3, "source": "local fallback"},
    ],
    "fashion": [
        {"name": "Campus Men's Running Shoes", "price": 1399.0, "rating": 4.0, "source": "local fallback"},
        {"name": "Allen Solly Men's Cotton Shirt", "price": 1199.0, "rating": 4.1, "source": "local fallback"},
        {"name": "Biba Women's Cotton Kurta", "price": 999.0, "rating": 4.2, "source": "local fallback"},
    ],
    "home": [
        {"name": "Prestige Iris Plus Mixer Grinder", "price": 2999.0, "rating": 4.1, "source": "local fallback"},
        {"name": "Wakefit Memory Foam Pillow", "price": 1299.0, "rating": 4.3, "source": "local fallback"},
        {"name": "Atomberg Renesa Ceiling Fan", "price": 3499.0, "rating": 4.2, "source": "local fallback"},
    ],
    "beauty": [
        {"name": "Minimalist Vitamin C Face Serum", "price": 699.0, "rating": 4.2, "source": "local fallback"},
        {"name": "Maybelline Fit Me Foundation", "price": 549.0, "rating": 4.1, "source": "local fallback"},
    ],
    "sports": [
        {"name": "Boldfit Yoga Mat", "price": 799.0, "rating": 4.2, "source": "local fallback"},
        {"name": "Lifelong PVC Dumbbell Set", "price": 1299.0, "rating": 4.0, "source": "local fallback"},
    ],
}


class CrawlerService:
    """
    Uses Firecrawl to scrape product trends from e-commerce sites.
    Extracts: product name, price, rating from the scraped content.
    """

    def __init__(self):
        if not FIRECRAWL_API_KEY:
            logger.warning("FIRECRAWL_API_KEY not set. Scraping will fail.")

    # ---------------------------
    # URL Generation
    # ---------------------------

    def _build_search_url(self, query: str, source: str = "amazon.in") -> str:
        """
        Dynamically build a search URL from the user's query.
        Supports Amazon India and Flipkart search pages.
        """
        encoded_query = quote_plus(query)
        template = SEARCH_SOURCES.get(source, SEARCH_SOURCES["amazon.in"])
        url = template.format(query=encoded_query)
        logger.info(f"Generated scrape URL: {url}")
        return url

    # ---------------------------
    # Price & Rating Extraction
    # ---------------------------

    def _extract_price(self, text: str) -> Optional[float]:
        """
        Extract the first price value found in a block of text.
        Handles ₹, Rs, INR, commas, and decimal formats.
        """
        # Remove commas from numbers like 1,499
        cleaned = text.replace(",", "")
        patterns = [
            r'(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)',  # ₹1499 or Rs 1,499
            r'(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|inr)',  # 1499 ₹
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    # Sanity check: products between ₹10 and ₹10,00,000
                    if 100 <= val <= 1_000_000:
                        return val
                except ValueError:
                    pass
        return None

    def _extract_rating(self, text: str) -> Optional[float]:
        """
        Extract a star rating (1.0–5.0) from text.
        Common patterns: '4.3 out of 5', '4.3 stars', '4.5/5'
        """
        patterns = [
            r'(\d\.\d)\s*out\s*of\s*5',
            r'(\d\.\d)\s*stars?',
            r'(\d\.\d)\s*/\s*5',
            r'rated?\s*(\d\.\d)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    if 1.0 <= val <= 5.0:
                        return val
                except ValueError:
                    pass
        return None

    # ---------------------------
    # Firecrawl API Call
    # ---------------------------

    async def _firecrawl_scrape(self, url: str) -> Optional[str]:
        """
        Call Firecrawl's /scrape endpoint and return the markdown content.
        """
        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Firecrawl returns data.data.markdown
            return data.get("data", {}).get("markdown", "")

    async def _firecrawl_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Use Firecrawl search as a fallback when a store search page blocks scraping.
        Search results usually include titles, descriptions, and URLs that still
        contain usable product names, prices, and ratings.
        """
        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": f"{query} price rating India shopping",
            "limit": 10,
            "location": "India",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FIRECRAWL_BASE_URL}/search",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        products: List[Dict[str, Any]] = []
        for item in data.get("data", []):
            title = (item.get("title") or "").strip()
            description = (item.get("description") or "").strip()
            url = item.get("url") or ""
            text = " ".join(part for part in [title, description] if part)

            if not text:
                continue

            price = self._extract_price(text)
            rating = self._extract_rating(text)
            name = self._extract_product_name(title, description)

            if not name:
                continue

            product = {
                "name": name,
                "price": price,
                "rating": rating if rating else 0.0,
                "url": url,
                "source": urlparse(url).netloc or "web search",
            }
            if not any(p["name"][:40].lower() == product["name"][:40].lower() for p in products):
                products.append(product)

            if len(products) >= 10:
                break

        logger.info(f"Parsed {len(products)} products from Firecrawl search")
        return products

    # ---------------------------
    # Product Parsing
    # ---------------------------

    def _parse_products(self, markdown: str, source: str) -> List[Dict[str, Any]]:
        """
        Parse scraped markdown content into structured product records.
        Each product block is heuristically identified and split.

        Returns list of:
          { "name": str, "price": float|None, "rating": float|None, "source": str }
        """
        products = []

        if not markdown:
            return products

        # Split markdown into lines and process in sliding windows
        lines = [line.strip() for line in markdown.split("\n") if line.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]
            name = self._extract_markdown_product_name(line)

            # Product names tend to be lines that are reasonably long (title-like)
            # and not purely numeric or UI chrome
            is_product_name = (
                bool(name)
                and len(name) > 15
                and len(name) < 220
                and not line.startswith("#")
                and not line.startswith("|")
                and self._looks_like_product_name(name)
            )

            if is_product_name:
                # Look around nearby lines for price/rating.
                context = " ".join(lines[i:i+8])
                price = self._extract_price(context)
                rating = self._extract_rating(context)

                if price is not None:  # Only include if we found a price
                    product = {
                        "name": name[:120],  # Cap name length
                        "price": price,
                        "rating": rating if rating else 0.0,
                        "url": self._build_search_url(name, source),
                        "source": source
                    }
                    # Deduplicate by name similarity
                    if not any(p["name"][:30] == product["name"][:30] for p in products):
                        products.append(product)

                    if len(products) >= 15:  # Cap at 15 raw products
                        break

            i += 1

        logger.info(f"Parsed {len(products)} products from markdown")
        return products

    def _extract_markdown_product_name(self, line: str) -> str:
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', line)
        link_match = re.search(r'\[\*\*(.*?)\*\*\]\(', text)
        if not link_match:
            link_match = re.search(r'\[([^\]]{20,})\]\(', text)
        text = link_match.group(1) if link_match else text
        text = re.sub(r'^\d+\.\s*', '', text)
        text = re.sub(r'\*\*|\\|\[|\]', '', text)
        text = re.sub(r'\s+', ' ', text).strip(" -|.,")
        return text

    def _looks_like_product_name(self, text: str) -> bool:
        bad_patterns = [
            r'\b(sponsored|let us know|bought in past month|price, product page|m\.r\.p|previous page|next page)\b',
            r'\b(you are seeing this ad|shop now|amazon\'?s choice|choicefor|limited time deal)\b',
            r'^₹',
            r'^price',
        ]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in bad_patterns):
            return False

        product_words = [
            "laptop", "notebook", "vivobook", "aspire", "inspiron", "vostro",
            "ideapad", "thinkpad", "pavilion", "macbook", "chromebook",
            "earbuds", "headphones", "phone", "tablet", "monitor",
        ]
        brand_words = [
            "acer", "asus", "dell", "hp", "lenovo", "msi", "apple", "realme",
            "oneplus", "boat", "goboult", "boult", "mivi", "sony", "samsung",
        ]
        lowered = text.lower()
        return any(word in lowered for word in product_words + brand_words)

    def _fallback_products(self, query: str) -> List[Dict[str, Any]]:
        """
        Provide useful demo recommendations when Firecrawl is not configured or
        the network is unavailable. These are marked clearly as local fallback
        data and still pass through the normal ranking/budget pipeline.
        """
        lowered = query.lower()
        selected_category = "electronics"

        phone_terms = [
            "phone", "phones", "smartphone", "smartphones", "mobile", "mobiles",
            "iphone", "iphones", "samsung", "realme", "redmi", "oneplus",
            "nokia", "motorola", "infinix", "oppo", "vivo",
        ]
        audio_terms = ["earbud", "earbuds", "headphone", "headphones", "speaker", "headset", "airpods"]
        electronics_terms = ["laptop", "laptops", "tv", "television", "ac", "air conditioner", "monitor", "camera"]
        fashion_terms = ["shoe", "shoes", "shirt", "shirts", "kurta", "dress", "jeans", "sneaker", "sneakers", "sunglasses", "jacket", "bag", "handbag", "watch", "cap", "hat", "boots", "sandals"]
        home_terms = ["mixer", "grinder", "pillow", "fan", "kitchen", "home", "mattress", "sofa", "table", "chair", "curtain", "storage", "cookware"]
        beauty_terms = ["serum", "foundation", "skincare", "lipstick", "moisturizer", "perfume", "shampoo", "conditioner", "mascara", "eyeliner", "blush"]
        sports_terms = ["yoga", "dumbbell", "fitness", "running", "gym", "cycle", "bicycle", "cricket", "football", "badminton", "tennis", "protein", "mat"]

        if any(term in lowered for term in phone_terms):
            selected_category = "electronics_phone"
        elif any(term in lowered for term in audio_terms):
            selected_category = "electronics_audio"
        elif any(term in lowered for term in electronics_terms):
            selected_category = "electronics"
        elif any(term in lowered for term in fashion_terms):
            selected_category = "fashion"
        elif any(term in lowered for term in home_terms):
            selected_category = "home"
        elif any(term in lowered for term in beauty_terms):
            selected_category = "beauty"
        elif any(term in lowered for term in sports_terms):
            selected_category = "sports"

        if selected_category not in FALLBACK_PRODUCTS:
            selected_category = "electronics"

        products = [dict(product) for product in FALLBACK_PRODUCTS.get(selected_category, [])]
        for product in products:
            product["url"] = self._build_search_url(product["name"], "amazon.in")

        logger.info(
            "Using %s local fallback products for category '%s'",
            len(products),
            selected_category,
        )
        return products

    def _dedupe_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for product in products:
            name = product.get("name") or ""
            key = re.sub(r'[^a-z0-9]+', '', name.lower())[:60]
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(product)

        return deduped

    async def _scrape_store(self, query: str, source: str) -> List[Dict[str, Any]]:
        url = self._build_search_url(query, source)
        logger.info(f"Scraping {source} URL: {url}")

        markdown = await self._firecrawl_scrape(url)
        products = self._parse_products(markdown, source)
        logger.info(f"Parsed {len(products)} products from {source}")
        return products

    def _extract_product_name(self, title: str, description: str) -> str:
        """
        Pick a product-like name from a search result. Generic search-page titles
        are replaced with the first descriptive phrase from the result snippet.
        """
        generic_title = re.search(r'\b(best|top|under|search|results?)\b', title, re.IGNORECASE)
        generic_description = re.search(r'\b(verified reviews?|reviews?|ratings?)\b', description, re.IGNORECASE)
        candidate = description if generic_title and description and not generic_description else title or description
        candidate = re.split(r'\s+[·|]\s+| - Amazon\.in| - Flipkart|\. ', candidate, maxsplit=1)[0]
        candidate = re.sub(r'\s+', ' ', candidate).strip(" -|·")
        return candidate[:120]

    def _extract_product_name(self, title: str, description: str) -> str:
        """
        Pick a product-like name from a search result. Generic listing pages
        often hide the real product name in the description, so split snippets
        into fragments and choose the first product-looking phrase.
        """
        title = re.sub(r'\s+', ' ', title or '').strip()
        description = re.sub(r'\s+', ' ', description or '').strip()

        generic_pattern = re.compile(
            r'\b(best|top|under|search|results?|list of|buy latest|view popular|youtube|quora)\b',
            re.IGNORECASE,
        )
        raw_candidate = description if generic_pattern.search(title) and description else title or description

        fragments = re.split(r'\s*(?:;|\|| - Amazon\.in| - Flipkart|\.{2,})\s*', raw_candidate)
        fragments.extend(re.split(r'\s*(?:;|\|| - Amazon\.in| - Flipkart|\.{2,})\s*', title))

        for fragment in fragments:
            cleaned = self._clean_product_name_fragment(fragment)
            if cleaned and not generic_pattern.search(cleaned):
                return cleaned[:120]

        fallback = self._clean_product_name_fragment(raw_candidate)
        return fallback[:120] if fallback else ""

    def _clean_product_name_fragment(self, fragment: str) -> str:
        fragment = re.sub(r'\s+', ' ', fragment or '').strip(" -|;,.")
        if not fragment or not re.search(r'[A-Za-z]', fragment):
            return ""

        skip_patterns = [
            r'\b(under|best|top|view popular|buy latest|verified reviews?|reviews?|ratings?)\b',
            r'\b(price in india|specs|features|launched|youtube|quora)\b',
            r'^\d+',
        ]
        if any(re.search(pattern, fragment, re.IGNORECASE) for pattern in skip_patterns):
            return ""

        fragment = re.split(r'\s*(?:₹|rs\.?|inr)\s*\d', fragment, maxsplit=1, flags=re.IGNORECASE)[0]
        fragment = re.sub(r'\b(?:apr|may|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar),?\s*\d{4}\b', '', fragment, flags=re.IGNORECASE)
        fragment = fragment.replace(". ", " ")
        fragment = re.sub(r'\s+', ' ', fragment).strip(" -|;,.")

        if len(fragment) < 4:
            return ""
        return fragment

    # ---------------------------
    # Public Interface
    # ---------------------------

    async def scrape_products(self, query: str) -> List[Dict[str, Any]]:
        """
        Main entry point: scrape products for a given query.
        Returns parsed list of product dicts.
        Includes simple in-memory caching.
        """
        cache_key = query.lower().strip()

        # Return cached result if available
        if cache_key in _scrape_cache:
            logger.info(f"Cache hit for query: '{query}'")
            return _scrape_cache[cache_key]

        if not FIRECRAWL_API_KEY:
            logger.warning("FIRECRAWL_API_KEY is not configured. Using local fallback products.")
            products = self._fallback_products(query)
            _scrape_cache[cache_key] = products
            return products

        try:
            scrape_results = await asyncio.gather(
                *(self._scrape_store(query, source) for source in SEARCH_SOURCES),
                return_exceptions=True,
            )

            products: List[Dict[str, Any]] = []
            for source, result in zip(SEARCH_SOURCES, scrape_results):
                if isinstance(result, Exception):
                    logger.warning(f"{source} scrape failed: {result}")
                    continue
                products.extend(result)

            products = self._dedupe_products(products)

            if not products:
                logger.warning("Store scrapes returned no products. Falling back to Firecrawl search.")
                products = await self._firecrawl_search(query)

            # Cache result
            _scrape_cache[cache_key] = products
            return products

        except httpx.HTTPStatusError as e:
            logger.error(f"Firecrawl HTTP error: {e.response.status_code} - {e.response.text}")
            products = self._fallback_products(query)
            _scrape_cache[cache_key] = products
            return products
        except httpx.RequestError as e:
            logger.error(f"Firecrawl request error: {e}")
            products = self._fallback_products(query)
            _scrape_cache[cache_key] = products
            return products
        except Exception as e:
            logger.error(f"Unexpected scraping error: {e}", exc_info=True)
            products = self._fallback_products(query)
            _scrape_cache[cache_key] = products
            return products
