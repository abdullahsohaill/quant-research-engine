# 📊 Quant Research Engine

> **Autonomous Financial Analysis Engine** — Receives natural language queries like *"Analyze NVIDIA vs AMD"* and delivers structured investment memos with real-time data, quantitative analysis, and AI-generated recommendations.

**Built using native SDKs and raw tool-calling loops to ensure a lean, production-ready architecture without the overhead of high-level frameworks.**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-8B5CF6)](https://modelcontextprotocol.io)

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│              React/TypeScript Frontend                   │
│         (Chat Interface + Markdown Renderer)             │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP POST /api/analyze
                           │ SSE /api/analyze/stream
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                         │
│  ┌───────────────────────────────────────────────────┐   │
│  │         Native Tool-Calling Loop                   │   │
│  │    (Google GenAI SDK — No LangChain/LangGraph)    │   │
│  │                                                    │   │
│  │  while has_function_call(response):                │   │
│  │      result = execute_mcp_tool(function_call)      │   │
│  │      history.append(function_response(result))     │   │
│  │      response = gemini.generate(history)           │   │
│  └──────────────┬────────────┬───────────────────────┘   │
│                 │            │                            │
│  ┌──────────────▼──┐  ┌─────▼──────────────┐            │
│  │  Input/Output    │  │  Critic Agent       │            │
│  │  Guardrails      │  │  (Quality Review)   │            │
│  │  - SQL Injection │  │  - Fact Checking    │            │
│  │  - Prompt Inject │  │  - Consistency      │            │
│  │  - PII Detection │  │  - Completeness     │            │
│  └─────────────────┘  └────────────────────┘            │
│                 │            │                            │
│  ┌──────────────▼────────────▼───────────────────────┐   │
│  │           MCP Client (Tool Registry)               │   │
│  │    Discovers tools → Converts to GenAI format      │   │
│  │    Routes tool calls → Returns results             │   │
│  └──────────┬─────────────────────┬──────────────────┘   │
└─────────────┼─────────────────────┼──────────────────────┘
              │                     │
   ┌──────────▼──────────┐  ┌──────▼──────────────┐
   │  Financial Data      │  │  PostgreSQL          │
   │  MCP Server          │  │  MCP Server          │
   │  (FastMCP + yfinance)│  │  (FastMCP + SQL)     │
   │                      │  │                      │
   │  Tools:              │  │  Tools:              │
   │  • get_stock_info    │  │  • execute_read_sql  │
   │  • get_price_history │  │  • get_table_schema  │
   │  • get_fundamentals  │  │  • get_sample_data   │
   │  • get_earnings      │  │                      │
   │  • compare_stocks    │  │  Security:           │
   │                      │  │  • SELECT-only guard │
   │                      │  │  • Keyword blocklist │
   └──────────────────────┘  └──────┬──────────────┘
                                    │
                             ┌──────▼──────────┐
                             │   PostgreSQL 16   │
                             │   (Stock Data)    │
                             │                   │
                             │   Tables:          │
                             │   • stocks         │
                             │   • stock_prices   │
                             │   • earnings       │
                             └───────────────────┘
```

## 🌟 Key Features

### AI Engineering
- **Native Tool-Calling Loop** — Built with raw Python `while` loops and the Google GenAI SDK. No LangChain, no LangGraph. Proves deep understanding of how LLMs work under the hood.
- **MCP Protocol Integration** — Financial data and SQL tools exposed as MCP servers using FastMCP, discovered and consumed by the orchestrator as an MCP client.
- **Multi-Agent Architecture** — Analyst agent generates reports, Critic agent reviews for accuracy and consistency.
- **Streaming Analysis** — Real-time progress via Server-Sent Events (SSE).

### Security & Safety
- **SQL Injection Prevention** — Defense-in-depth: guardrails in both the orchestrator AND the MCP server. Only `SELECT` queries pass. `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER` are all blocked.
- **Prompt Injection Detection** — Input guardrails scan for common injection patterns.
- **PII Detection** — Output guardrails scan for SSN, credit card, and email patterns before delivery.
- **Financial Disclaimer** — Auto-injected on all reports.

### Full-Stack
- **Python Backend** — FastAPI with async support, Pydantic validation, and proper lifecycle management.
- **TypeScript Frontend** — React 19 with a premium dark-mode financial dashboard UI.
- **Docker Compose** — Full system deployment with 5 services (Postgres, 2 MCP servers, backend, frontend).

### Financial Analysis
- **50 S&P 500 Stocks** — Pre-seeded database with fundamentals, historical prices, and earnings data.
- **Real-Time Data** — Live data fetching via yfinance for any publicly traded stock.
- **Structured Investment Memos** — Professional format with executive summary, valuation tables, risk factors, and buy/sell recommendations.

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- A Gemini API key ([get one free](https://aistudio.google.com/apikey))

### 1. Clone & Configure

```bash
git clone https://github.com/yourusername/quant-research-engine.git
cd quant-research-engine

# Copy environment template and add your Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-here
```

### 2. Launch with Docker Compose

```bash
docker-compose up --build
```

This starts all 5 services:
| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Financial database |
| Financial MCP | 8001 | yfinance data server |
| Postgres MCP | 8002 | SQL query server |
| Backend | 8000 | FastAPI orchestrator |
| Frontend | 3000 | React dashboard |

### 3. Seed the Database

```bash
# Via API
curl -X POST http://localhost:8000/api/seed

# Or run the script directly
python scripts/seed.py --quick  # 5 stocks for testing
python scripts/seed.py          # Full 50 stocks
```

### 4. Start Analyzing

Open [http://localhost:3000](http://localhost:3000) and try:
- "Analyze NVIDIA stock"
- "Compare AAPL vs MSFT for investment"
- "Give me a buy/sell brief on AMD vs INTC"
- "What are the best semiconductor stocks by P/E ratio?"

---

## 🏃 Local Development (Without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\\Scripts\\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GEMINI_API_KEY=your-key-here
export POSTGRES_HOST=localhost

# Start MCP servers (in separate terminals)
python -m backend.run_mcp --server financial --port 8001
python -m backend.run_mcp --server postgres --port 8002

# Start the backend
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 📁 Project Structure

```
quant-research-engine/
├── backend/
│   ├── main.py                     # FastAPI application
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── run_mcp.py                  # MCP server runner
│   ├── Dockerfile
│   ├── requirements.txt
│   │
│   ├── data/
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── database.py             # Async/sync DB connections
│   │   └── seed_database.py        # S&P 500 data seeder
│   │
│   ├── mcp_servers/
│   │   ├── financial_data_mcp.py   # yfinance MCP server (5 tools)
│   │   └── postgres_mcp.py         # PostgreSQL MCP server (3 tools)
│   │
│   ├── orchestrator/
│   │   ├── engine.py               # Native tool-calling loop ⭐
│   │   ├── tool_registry.py        # MCP → GenAI bridge
│   │   ├── prompts.py              # System prompts
│   │   └── guardrails.py           # Input/Output/SQL safety
│   │
│   └── schemas/
│       └── api.py                  # Pydantic request/response models
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Main application
│   │   ├── App.css                 # Component styles
│   │   ├── index.css               # Design system
│   │   ├── api/client.ts           # API client (sync + SSE)
│   │   ├── types/index.ts          # TypeScript types
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── ChatInput.tsx
│   │       ├── LoadingState.tsx
│   │       └── AnalysisReport.tsx
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── scripts/
│   └── seed.py                     # Standalone seeder
│
├── docker-compose.yml              # Full system deployment
├── .env.example                    # Environment template
└── README.md
```

---

## 🔧 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **LLM** | Google Gemini 2.5 Flash | Native tool-calling via GenAI SDK |
| **Protocol** | MCP (Model Context Protocol) | Standardized tool exposure |
| **MCP SDK** | FastMCP | MCP server/client implementation |
| **Backend** | FastAPI + Uvicorn | Async REST API + SSE streaming |
| **Database** | PostgreSQL 16 | Financial data persistence |
| **ORM** | SQLAlchemy (async) | Database models & queries |
| **Data** | yfinance | Real-time financial data |
| **Frontend** | React 19 + TypeScript | User interface |
| **Build** | Vite | Frontend build toolchain |
| **Deploy** | Docker Compose | Multi-service deployment |

---

## 🔒 Security Model

### Defense-in-Depth for SQL Injection

```
User Input → [Input Guardrail] → AI Orchestrator → SQL Output
                                       ↓
                              [SQL Guardrail (orchestrator)]
                                       ↓
                              [SQL Guardrail (MCP server)]
                                       ↓
                              PostgreSQL (SELECT only)
```

**Three layers of protection:**
1. **Input Guardrail** — Blocks prompt injection attempts before they reach the LLM
2. **Orchestrator SQL Guardrail** — Validates AI-generated SQL before execution
3. **MCP Server SQL Guardrail** — Independent validation at the execution layer

### Blocked SQL Patterns
```
DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE,
GRANT, REVOKE, EXEC, EXECUTE, COPY, LOAD, pg_*, xp_*, sp_*,
INFORMATION_SCHEMA, pg_catalog, multi-statement queries
```

---

## 📊 Sample Output

**Query:** *"Analyze NVIDIA vs AMD for investment"*

The engine generates a structured Investment Memo including:
- ✅ Executive Summary with buy/sell recommendation
- ✅ Side-by-side valuation comparison table (P/E, P/B, EV/EBITDA, PEG)
- ✅ Profitability metrics (margins, ROE, ROA)
- ✅ Revenue growth and earnings trend analysis
- ✅ Balance sheet health assessment
- ✅ Risk factors (5+ specific risks)
- ✅ Analyst consensus and price targets
- ✅ Quality review by the Critic Agent

---

## 🏭 Design Philosophy

> *"We prefer lean integrations over heavy frameworks, and expect you to be comfortable working close to the API level."*

This project deliberately avoids LangChain, LangGraph, and other high-level abstraction frameworks. Instead:

- **The orchestrator** is a `while` loop with a Python `list` for conversation history
- **Tool calling** is handled manually by parsing `function_call` responses from the Gemini API
- **MCP integration** is done through the native `fastmcp` client, not wrapped in any framework
- **State management** uses plain Python data structures, not a complex graph

This demonstrates deep understanding of how LLMs, tool-calling, and agentic systems work at the API level.

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.
