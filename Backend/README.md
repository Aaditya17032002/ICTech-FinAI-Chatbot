# Investment Insight Chatbot - Backend

A production-grade, multi-agent AI system for investment advice built with FastAPI, PydanticAI, and Groq.

## Features

- **Multi-Agent Architecture**: Three specialized agents working together
  - **Router Agent** (Compound Beta): Ultra-fast tool calling for data fetching
  - **Analyst Agent** (Llama 4 Scout): Smart explanations and general advice
  - **Reasoning Agent** (Qwen3-32B): Complex calculations and comparisons
- **Real-time Data**: Live mutual fund data from AMFI India, stock data from Yahoo Finance
- **Type-Safe AI**: PydanticAI ensures structured, validated outputs
- **Conversation Memory**: Session-based context for natural conversations
- **Response Caching**: DiskCache for improved performance
- **Streaming Responses**: SSE support for real-time token streaming
- **Compliance Built-in**: Mandatory risk disclaimers and source citations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
├─────────────────────────────────────────────────────────────┤
│  API Layer (Routes)                                          │
│  ├── /chat          - Chat with AI advisor                   │
│  ├── /chat/stream   - Streaming chat responses               │
│  ├── /funds/search  - Search mutual funds                    │
│  └── /funds/{code}  - Get fund details                       │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                               │
│  ├── ChatService         - Conversation management           │
│  ├── MutualFundService   - Fund business logic               │
│  └── StockService        - Stock business logic              │
├─────────────────────────────────────────────────────────────┤
│  Multi-Agent Layer (PydanticAI + Groq)                       │
│  ├── Router Agent        - Compound Beta (fast tool calls)   │
│  ├── Analyst Agent       - Llama 4 Scout (explanations)      │
│  ├── Reasoning Agent     - Qwen3-32B (complex analysis)      │
│  └── Tools               - Data fetching & calculations      │
├─────────────────────────────────────────────────────────────┤
│  Repository Layer                                            │
│  ├── FundRepository      - AMFI India (mftool)               │
│  ├── StockRepository     - Yahoo Finance (yfinance)          │
│  └── CacheRepository     - DiskCache                         │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Agent Strategy

The system uses a **"Team of Specialists"** approach:

1. **Router Agent (Compound Beta)** - The "Researcher"
   - Ultra-fast tool calling (3x lower latency)
   - Fetches data from AMFI India and Yahoo Finance
   - Designed for production systems

2. **Analyst Agent (Llama 4 Scout 17B)** - The "Explainer"
   - Mixture-of-Experts architecture
   - Writes clear, concise explanations
   - Handles general investment queries

3. **Reasoning Agent (Qwen3-32B)** - The "Thinker"
   - Native "Thinking Mode" for step-by-step reasoning
   - Handles CAGR calculations, risk assessments
   - Used for fund comparisons and recommendations

## Quick Start

### Prerequisites

- Python 3.11+
- Groq API key (free tier available)

### Installation

1. **Clone and navigate to backend**:
   ```bash
   cd backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

5. **Run the server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the API**:
   - API Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Health: http://localhost:8000/api/v1/health

## API Endpoints

### Chat

#### POST `/api/v1/chat`
Send a message to the investment advisor.

**Request:**
```json
{
  "message": "What are the top-performing mutual funds this year?",
  "session_id": null
}
```

**Response:**
```json
{
  "session_id": "abc123-uuid",
  "response": {
    "explanation": "Based on current data from AMFI India...",
    "data_points": [
      {
        "metric": "1Y Return",
        "value": "18.5%",
        "as_of_date": "2026-02-21"
      }
    ],
    "sources": [
      {
        "name": "AMFI India",
        "url": "https://www.amfiindia.com",
        "accessed_at": "2026-02-21T10:00:00Z"
      }
    ],
    "risk_disclaimer": "Mutual fund investments are subject to market risks...",
    "confidence_score": 0.85
  },
  "processing_time_ms": 1250,
  "cached": false
}
```

#### POST `/api/v1/chat/stream`
Stream response tokens via Server-Sent Events.

**Request:** Same as `/chat`

**Response:** SSE stream
```
event: token
data: {"token": "Based"}

event: token
data: {"token": " on"}

...

event: complete
data: {"response": {...}, "session_id": "abc123"}
```

### Funds

#### GET `/api/v1/funds/search?q=sbi&limit=10`
Search mutual funds by name.

**Response:**
```json
{
  "results": [
    {
      "scheme_code": "119598",
      "scheme_name": "SBI Bluechip Fund - Direct Plan - Growth",
      "category": "Equity - Large Cap",
      "nav": 85.67,
      "nav_date": "2026-02-20"
    }
  ],
  "total": 15
}
```

#### GET `/api/v1/funds/{scheme_code}`
Get detailed fund information.

**Response:**
```json
{
  "scheme_code": "119598",
  "scheme_name": "SBI Bluechip Fund - Direct Plan - Growth",
  "fund_house": "SBI Mutual Fund",
  "category": "Equity - Large Cap",
  "nav": 85.67,
  "nav_date": "2026-02-20",
  "returns": {
    "1m": "2.3%",
    "3m": "5.1%",
    "6m": "8.7%",
    "1y": "18.5%",
    "3y": "15.2%",
    "5y": "12.8%"
  },
  "aum": null,
  "expense_ratio": null
}
```

#### POST `/api/v1/funds/compare`
Compare multiple funds.

**Request:**
```json
["119598", "118989", "120503"]
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Settings management
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py            # Chat endpoints
│   │   │   ├── funds.py           # Fund endpoints
│   │   │   └── health.py          # Health check
│   │   └── dependencies.py        # DI providers
│   │
│   ├── services/
│   │   ├── chat_service.py        # Conversation logic
│   │   ├── mutual_fund_service.py # Fund business logic
│   │   └── stock_service.py       # Stock business logic
│   │
│   ├── agents/
│   │   ├── investment_agent.py    # PydanticAI agent
│   │   ├── prompts.py             # System prompts
│   │   └── tools/
│   │       ├── researcher.py      # Data fetching
│   │       ├── analyst.py         # Analysis
│   │       └── compliance.py      # Risk disclaimers
│   │
│   ├── repositories/
│   │   ├── cache_repository.py    # DiskCache
│   │   ├── fund_repository.py     # AMFI/mftool
│   │   └── stock_repository.py    # Yahoo Finance
│   │
│   ├── models/
│   │   ├── schemas.py             # API schemas
│   │   ├── domain.py              # Domain entities
│   │   └── agent_outputs.py       # Agent response models
│   │
│   └── utils/
│       ├── calculations.py        # CAGR, returns
│       └── formatters.py          # Data formatting
│
├── data/
│   └── fund_mappings.json         # Popular fund codes
│
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | Required |
| `ROUTER_MODEL` | Fast tool-calling model | `groq/compound-beta` |
| `ANALYST_MODEL` | Explanation model | `groq/meta-llama/llama-4-scout-17b-16e-instruct` |
| `REASONING_MODEL` | Complex reasoning model | `groq/qwen/qwen3-32b` |
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/investment.db` |
| `CACHE_DIR` | Cache directory | `./data/cache` |
| `CACHE_TTL_HOURS` | Cache expiry | `24` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Example Queries

The chatbot can handle queries like:

- "What are the top-performing mutual funds this year?"
- "Compare SBI Bluechip vs HDFC Top 100"
- "Is it a good time to invest in index funds?"
- "What does CAGR mean and why does it matter?"
- "Show me the NAV of Axis Midcap Fund"
- "What's the current NIFTY 50 level?"

## Tech Stack

- **Framework**: FastAPI
- **AI Agent**: PydanticAI with Groq
- **LLMs**: 
  - Groq Compound Beta (Router)
  - Llama 4 Scout 17B (Analyst)
  - Qwen3-32B (Reasoning)
- **Data Sources**: mftool (AMFI India), yfinance (Yahoo Finance)
- **Caching**: DiskCache
- **Streaming**: SSE (sse-starlette)

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Quality
```bash
# Format
black app/

# Lint
ruff check app/

# Type check
mypy app/
```

## License

MIT License

## Disclaimer

This API provides information for educational purposes only. Investment in securities market are subject to market risks. Read all the related documents carefully before investing. Please consult a qualified financial advisor before making investment decisions.
