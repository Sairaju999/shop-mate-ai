# 🛒 ShopMate AI

**Intelligent Retail Recommendation System** powered by **Gemini AI** + **Firecrawl** + **Memento-style Memory**

---

## 🏗️ Architecture

```
User → POST /recommend
         │
         ▼
   Memento Memory          ← Extracts: category, budget, history
         │
         ▼
   Firecrawl Scraper       ← Scrapes real-time products from Amazon
         │
         ▼
   Product Processor       ← Filters by budget, ranks by rating
         │
         ▼
   Gemini LLM              ← Generates personalized recommendations
         │
         ▼
   JSON Response           ← top 3–5 products with explanations
```

---

## 📁 Project Structure

```
shopmate-ai/
│
├── app.py                  # FastAPI app entry point
├── routes/
│   └── recommend.py        # API endpoint definitions
├── services/
│   ├── memory.py           # Memento-style user memory
│   ├── crawler.py          # Firecrawl product scraping
│   ├── llm.py              # Gemini API integration
│   └── processor.py        # Product ranking & filtering
├── data/
│   └── users.json          # Persistent user memory store
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
└── README.md
```

---

## ⚙️ Setup

### 1. Clone & enter the project

```bash
git clone <your-repo>
cd shopmate-ai
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# OR
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
GEMINI_API_KEY=your_gemini_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

**Get API Keys:**
- Gemini: https://aistudio.google.com/app/apikey
- Firecrawl: https://firecrawl.dev

### 5. Run the server

```bash
uvicorn app:app --reload --port 8000
```

---

## 🔌 API Endpoints

### `POST /recommend`

Generate personalized product recommendations.

**Request:**
```json
{
  "user_id": "alice",
  "query": "wireless headphones under 5000"
}
```

**Response:**
```json
{
  "user_id": "alice",
  "query": "wireless headphones under 5000",
  "memory_snapshot": {
    "history": ["wireless headphones under 5000"],
    "category": "electronics",
    "budget": 5000.0
  },
  "recommendations": "Recommended Products:\n\n1. Sony WH-CH720N\n   - Price: ₹4,999\n   - Rating: 4.3/5\n   - Reason: ...",
  "products_analyzed": 8
}
```

---

### `GET /memory/{user_id}`

Retrieve stored memory profile for a user.

```bash
curl http://localhost:8000/memory/alice
```

**Response:**
```json
{
  "user_id": "alice",
  "memory": {
    "history": ["wireless headphones under 5000", "gaming mouse"],
    "category": "electronics",
    "budget": 5000.0
  }
}
```

---

### `POST /memory/update`

Manually update user category or budget.

**Request:**
```json
{
  "user_id": "alice",
  "category": "fashion",
  "budget": 2000
}
```

---

### `GET /health`

Health check endpoint.

---

## 🧠 How Memento Memory Works

Every time a user sends a query, the system:

1. **Appends** the query to the user's history (last 20 kept)
2. **Extracts category** by matching keywords (electronics, fashion, home, etc.)
3. **Extracts budget** from natural language ("under 5000", "below 10k", "₹2000")
4. **Persists** the updated profile to `data/users.json`

This simulates a Memento-style memory where the AI "remembers" the user's preferences across sessions without needing a database.

---

## 📊 Ranking Logic

Before sending products to Gemini, the processor:

1. **Filters** out products exceeding the user's budget (10% buffer allowed)
2. **Scores** each product: `score = (rating × 2) + budget_proximity_bonus`
3. **Sorts** descending and sends top 10 to Gemini
4. Gemini picks the **final 3–5** with personalized reasoning

---

## 🔍 Sample Queries

```
"best gaming laptop under 70000"
"wireless earbuds below 3k"
"running shoes for men under 2000"
"kitchen blender good rating"
"cotton kurta for women"
```

---

## 🛠️ Development Notes

- Scraped product results are **cached in-memory** per session to reduce Firecrawl API calls
- User memories are **persisted across restarts** via `data/users.json`
- History is capped at **last 20 queries** per user (sliding window)
- Budget extraction handles: `₹`, `Rs`, `INR`, `k` shorthand, natural language phrases

---

## 📝 License

MIT License — free to use, modify, and distribute.
