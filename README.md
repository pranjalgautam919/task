# Analytics Backend Service

A high-performance backend service built with **FastAPI** and **PostgreSQL** that ingests large volumes of e-commerce data (1.3M+ records), processes it, and exposes analytics endpoints with response times consistently **below 2 seconds**.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Database Design](#database-design)
- [Performance Optimization](#performance-optimization)
- [Load Testing](#load-testing)
- [Project Structure](#project-structure)

---

## 🏗️ Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐
│   Data Generator    │────>│     PostgreSQL       │
│  (Faker + Seed=42)  │     │   (Primary Store)    │
│  100K + 1M + 200K   │     │                      │
└─────────────────────┘     │  - Tables + Indexes  │
                            │  - Materialized Views│
┌─────────────────────┐     │                      │
│   Mock APIs         │<────│                      │
│  (Paginated REST)   │     └──────────┬───────────┘
└────────┬────────────┘                │
         │                             │
┌────────▼────────────┐     ┌──────────▼───────────┐
│  Ingestion Service  │────>│      Redis           │
│  (Async + Batch)    │     │   (Cache Layer)      │
└─────────────────────┘     └──────────┬───────────┘
                                       │
                            ┌──────────▼───────────┐
                            │   Analytics APIs     │
                            │  (< 2s response)     │
                            └──────────────────────┘
```

### Data Flow

1. **Data Generation** → Faker generates 1.3M seeded records → bulk inserted via PostgreSQL COPY protocol
2. **Mock APIs** → Serve data from PostgreSQL with pagination (page/page_size)
3. **Ingestion Service** → Async HTTP client pulls from mock APIs → batch inserts into PostgreSQL
4. **Materialized Views** → Pre-aggregate data for instant analytics reads
5. **Redis Cache** → 60s TTL cache layer for analytics endpoints
6. **Analytics APIs** → Query materialized views + cache for sub-second responses

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | FastAPI (async) | High-performance API server |
| Database | PostgreSQL 16 | Primary data store |
| Cache | Redis 7 | Analytics result caching |
| ORM | SQLAlchemy 2.0 (async) | Database abstraction |
| HTTP Client | httpx (async) | Ingestion API calls |
| Data Gen | Faker (seeded) | Reproducible test data |
| Load Testing | Locust | Performance validation |
| Container | Docker + Compose | One-command deployment |

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose installed

### 1. Clone the Repository

```bash
git clone <repository-url>
cd task
```

### 2. Start All Services

```bash
docker-compose up --build
```

This single command:
- Starts **PostgreSQL 16** with health checks
- Starts **Redis 7** with health checks
- Generates **1.3M records** (100K customers + 1M orders + 200K refunds)
- Creates **materialized views** and **indexes**
- Starts the **FastAPI server** on port 8000

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

### 4. (Optional) Trigger Ingestion from Mock APIs

```bash
# Start ingestion
curl -X POST http://localhost:8000/api/ingest/start

# Check status
curl http://localhost:8000/api/ingest/status
```

### 5. Query Analytics

```bash
# Summary
curl http://localhost:8000/api/analytics/summary

# Top customers
curl http://localhost:8000/api/analytics/top-customers?limit=10

# Revenue trends
curl http://localhost:8000/api/analytics/revenue-trends?period=monthly

# Repeat customer revenue
curl http://localhost:8000/api/analytics/repeat-customers/revenue
```

---

## 📡 API Documentation

Interactive documentation available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

### Mock APIs (Data Source)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mock/customers?page=1&page_size=1000` | GET | Paginated customers |
| `/api/mock/orders?page=1&page_size=1000` | GET | Paginated orders |
| `/api/mock/refunds?page=1&page_size=1000` | GET | Paginated refunds |

**Pagination Response Format:**
```json
{
    "data": [...],
    "page": 1,
    "page_size": 1000,
    "total_count": 100000,
    "total_pages": 100
}
```

### Ingestion APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest/start` | POST | Trigger ingestion pipeline |
| `/api/ingest/status` | GET | Check ingestion progress |

### Analytics APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/summary` | GET | Total orders, revenue, refunds, net revenue, AOV |
| `/api/analytics/repeat-customers/revenue` | GET | Revenue from repeat customers |
| `/api/analytics/revenue-trends?period=daily` | GET | Revenue trends (daily/monthly) |
| `/api/analytics/top-customers?limit=10` | GET | Top N customers by spend |

**Sample Analytics Summary Response:**
```json
{
    "total_orders": 857143,
    "total_revenue": 858271456.78,
    "total_refunds": 120000,
    "total_refund_amount": 30245678.90,
    "net_revenue": 828025777.88,
    "avg_order_value": 1001.32
}
```

---

## 🗄️ Database Design

### Entity Relationship

```
customers (100K)
    ├── id (UUID, PK)
    ├── name, email (unique), phone
    ├── address, city, state, country, zip_code
    └── created_at

orders (1M)
    ├── id (UUID, PK)
    ├── customer_id (FK → customers.id)
    ├── total_amount, status, order_date
    └── created_at

refunds (200K)
    ├── id (UUID, PK)
    ├── order_id (FK → orders.id, unique)
    ├── refund_amount, reason, status, refund_date
    └── created_at
```

### Strategic Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_orders_customer_id` | customer_id | Fast customer-order joins |
| `idx_orders_status` | status | Filter cancelled orders |
| `idx_orders_order_date` | order_date | Revenue trends queries |
| `idx_orders_customer_amount` | (customer_id, total_amount) | Top customer aggregation |
| `idx_orders_status_amount` | (status, total_amount) | Revenue filtering |
| `idx_refunds_order_id` | order_id | Order-refund joins |
| `idx_refunds_status` | status | Filter by refund status |
| `idx_refunds_status_amount` | (status, refund_amount) | Refund aggregation |

### Materialized Views (Key Optimization)

| View | Purpose | Refresh |
|------|---------|---------|
| `mv_analytics_summary` | Single-row summary of all metrics | After ingestion |
| `mv_customer_spend` | Per-customer order count + spend | Concurrently |
| `mv_daily_revenue` | Daily order count + revenue | Concurrently |

---

## ⚡ Performance Optimization

### Strategy Overview

| Technique | Impact | Details |
|-----------|--------|---------|
| **Materialized Views** | **~100x faster** analytics reads | Pre-aggregated data; instant SELECT on single row |
| **Redis Caching** | **Sub-10ms** repeat queries | 60s TTL; auto-invalidated after ingestion |
| **Strategic Indexes** | **10-50x faster** JOINs/filters | Composite indexes for common query patterns |
| **COPY Protocol** | **5-10x faster** inserts | Bulk data loading bypasses standard INSERT |
| **Async I/O** | **High concurrency** | Non-blocking DB and HTTP operations |
| **Connection Pooling** | **Reduced overhead** | 20 pool + 10 overflow connections |
| **Batch Processing** | **Memory efficient** | 5K-50K record batches for inserts |

### Why Materialized Views?

Analytics queries on 1M+ rows typically require expensive `SUM`, `COUNT`, `GROUP BY`, and `JOIN` operations. By pre-computing these into materialized views:

- `GET /api/analytics/summary` → Reads 1 row from `mv_analytics_summary` instead of scanning 1M orders + 200K refunds
- `GET /api/analytics/top-customers` → Reads pre-sorted `mv_customer_spend` instead of aggregating 1M orders
- `GET /api/analytics/revenue-trends` → Reads pre-grouped `mv_daily_revenue` instead of grouping 1M orders

Views are refreshed after each ingestion cycle, so analytics data is always current.

---

## 📊 Load Testing

### Run Load Tests

```bash
# Install locust (if not using Docker)
pip install locust

# Headless mode — 50 users, 60 seconds
locust -f load_tests/locustfile.py --headless \
    -u 50 -r 10 --run-time 60s \
    --host http://localhost:8000 \
    --html load_tests/report.html

# Interactive mode with web UI
locust -f load_tests/locustfile.py --host http://localhost:8000
```

### Expected Results

With 50 concurrent users over 60 seconds:

| Endpoint | Avg (ms) | p95 (ms) | p99 (ms) |
|----------|----------|----------|----------|
| `/api/analytics/summary` | < 20 | < 50 | < 200 |
| `/api/analytics/repeat-customers/revenue` | < 20 | < 50 | < 200 |
| `/api/analytics/revenue-trends (daily)` | < 30 | < 100 | < 300 |
| `/api/analytics/revenue-trends (monthly)` | < 20 | < 50 | < 200 |
| `/api/analytics/top-customers` | < 20 | < 50 | < 200 |

All endpoints consistently respond in **< 2 seconds** even at p99 under load.

---

## 📁 Project Structure

```
task/
├── docker-compose.yml          # Docker orchestration (PG + Redis + App)
├── Dockerfile                  # Python 3.11 application container
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── .gitignore
├── README.md                   # This file
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point + lifespan
│   ├── config.py               # Pydantic settings from env vars
│   ├── database.py             # Async SQLAlchemy + materialized views
│   ├── models.py               # ORM models (Customer, Order, Refund)
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── data_generator.py       # Seeded Faker data generation
│   │
│   ├── routers/
│   │   ├── mock_api.py         # Paginated mock data endpoints
│   │   ├── ingestion.py        # Ingestion trigger + status
│   │   └── analytics.py        # Analytics query endpoints
│   │
│   ├── services/
│   │   ├── cache_service.py    # Redis caching layer
│   │   ├── analytics_service.py # Analytics query + cache logic
│   │   └── ingestion_service.py # Async ingestion pipeline
│   │
│   └── utils/
│       └── pagination.py       # Pagination helpers
│
├── scripts/
│   └── generate_data.py        # CLI data generation + DB seeding
│
└── load_tests/
    └── locustfile.py            # Locust load test definitions
```

---

## 🔧 Development

### Manual Setup (Without Docker)

```bash
# 1. Install PostgreSQL 16 and Redis 7

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with your database credentials

# 5. Generate data
python scripts/generate_data.py

# 6. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Rebuilding Data

```bash
# Drop existing data and regenerate
docker-compose down -v    # Remove volumes
docker-compose up --build # Rebuild and regenerate
```

---

## 📝 License

MIT
