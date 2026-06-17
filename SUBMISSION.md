# Assignment Submission — Analytics Backend Service

**Candidate:** Pranjal Gautam  
**GitHub Repository:** https://github.com/pranjalgautam919/task  
**Submission Date:** June 17, 2026

---

## 1. GitHub Repository

| Item | Link |
|------|------|
| **Repository** | https://github.com/pranjalgautam919/task |
| **Branch** | `main` |
| **Tech Stack** | FastAPI, PostgreSQL 16, Redis 7, SQLAlchemy 2.0, Docker |

The repository contains the full backend implementation: data generation, mock APIs, ingestion pipeline, analytics APIs, materialized views, Redis caching, Docker setup, and Locust load tests.

---

## 2. Setup Instructions

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git (optional, for cloning)

### Quick Start (Recommended — One Command)

```bash
git clone https://github.com/pranjalgautam919/task.git
cd task
cp .env.example .env
docker-compose up --build
```

This automatically:

1. Starts **PostgreSQL 16** and **Redis 7**
2. Generates **1.3M records** (100K customers + 1M orders + 200K refunds)
3. Creates **indexes** and **materialized views**
4. Starts the **FastAPI server** on port `8000`

**First startup takes 5–15 minutes** (data generation). Subsequent starts are faster if the database volume already has data.

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Analytics summary
curl http://localhost:8000/api/analytics/summary

# Interactive API docs
# Open in browser: http://localhost:8000/docs
```

### Optional: Trigger Ingestion Pipeline

```bash
curl -X POST http://localhost:8000/api/ingest/start
curl http://localhost:8000/api/ingest/status
```

### Rebuild from Scratch

```bash
docker-compose down -v
docker-compose up --build
```

### Manual Setup (Without Docker)

See [README.md](README.md#development) for PostgreSQL + Redis local setup.

---

## 3. API Documentation

### Interactive Docs (Swagger / ReDoc)

| Type | URL |
|------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |

### Mock APIs (Data Source)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mock/customers?page=1&page_size=1000` | GET | Paginated customers |
| `/api/mock/orders?page=1&page_size=1000` | GET | Paginated orders |
| `/api/mock/refunds?page=1&page_size=1000` | GET | Paginated refunds |

**Response format:**

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
| `/api/ingest/start` | POST | Start async ingestion from mock APIs |
| `/api/ingest/status` | GET | Check ingestion progress (Redis-backed) |

### Analytics APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/summary` | GET | Total orders, revenue, refunds, net revenue, AOV |
| `/api/analytics/repeat-customers/revenue` | GET | Revenue from repeat customers |
| `/api/analytics/revenue-trends?period=daily` | GET | Daily revenue trends |
| `/api/analytics/revenue-trends?period=monthly` | GET | Monthly revenue trends |
| `/api/analytics/top-customers?limit=10` | GET | Top N customers by spend |

**Sample `/api/analytics/summary` response:**

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

### Health Check

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Database + Redis connectivity status |

---

## 4. Architecture & Optimization Decisions

### 4.1 High-Level Architecture

```
Data Generator (Faker, seed=42)
        ↓ COPY protocol bulk insert
   PostgreSQL (primary store)
        ↓ paginated reads
   Mock APIs  ←── Ingestion Service (httpx async) ──→ PostgreSQL
        ↓
   Materialized Views (pre-aggregated analytics)
        ↓
   Redis Cache (60s TTL)
        ↓
   Analytics APIs (< 2s response)
```

**Why this design?**

- **Separation of concerns:** Mock APIs simulate an external data source; ingestion mimics a real ETL pipeline.
- **Async throughout:** FastAPI + asyncpg + httpx allow high concurrency without blocking threads.
- **Pre-computation over real-time aggregation:** Analytics on 1M+ rows at request time is too slow; materialized views shift cost to write/refresh time.

### 4.2 Database Design

**Tables:** `customers` (100K) → `orders` (1M) → `refunds` (200K)

| Design Choice | Rationale |
|---------------|-----------|
| UUID primary keys | Globally unique, safe for distributed ingestion |
| FK constraints with CASCADE | Referential integrity on deletes |
| Composite indexes | `(customer_id, total_amount)`, `(status, total_amount)` match analytics query patterns |
| `order_id` UNIQUE on refunds | One refund per order — business rule enforced at DB level |

**Materialized Views:**

| View | Purpose |
|------|---------|
| `mv_analytics_summary` | Single-row snapshot of all KPIs |
| `mv_customer_spend` | Per-customer order count + spend (top customers, repeat revenue) |
| `mv_daily_revenue` | Daily order count + revenue (trends) |

Refreshed after each ingestion cycle (`REFRESH MATERIALIZED VIEW CONCURRENTLY` where unique indexes allow it).

### 4.3 Performance Optimizations

| Technique | Impact | Implementation |
|-----------|--------|----------------|
| **Materialized views** | ~100× faster reads | Pre-aggregated data; analytics reads 1 row or indexed slices |
| **Redis caching** | Sub-10ms repeat queries | 60s TTL; auto-cleared after ingestion |
| **Strategic indexes** | 10–50× faster JOINs/filters | Status, date, composite amount indexes |
| **COPY protocol** | 5–10× faster bulk load | `scripts/generate_data.py` uses PostgreSQL COPY |
| **Batch inserts** | Memory-efficient ingestion | 5K-row batches with `ON CONFLICT DO NOTHING` |
| **Connection pooling** | Lower connection overhead | 20 pool + 10 overflow (SQLAlchemy async) |
| **Concurrent page fetch** | Faster ingestion | httpx + asyncio semaphore (10 concurrent) |
| **orjson serialization** | Faster cache read/write | Used in Redis cache layer |

### 4.4 Scalability Decisions

| Area | Approach |
|------|----------|
| **Horizontal API scaling** | Uvicorn multi-worker (4 workers); ingestion status stored in Redis (not in-memory) |
| **Database reads** | Materialized views + indexes reduce full table scans |
| **Cache layer** | Redis offloads repeated analytics queries |
| **Ingestion** | Async batch pipeline; idempotent inserts; configurable concurrency |
| **Future scaling** | Read replicas for analytics; partition `orders` by date; message queue for ingestion |

### 4.5 Code Quality

- **Layered architecture:** `routers` → `services` → `database`
- **Pydantic v2 schemas** for request/response validation
- **Type hints** throughout
- **Structured logging**
- **Environment-based config** via `.env` (secrets not committed)
- **Docker Compose** for reproducible one-command deployment

---

## 5. Load Test Results

### How to Run Load Tests

**Prerequisite:** App must be running (`docker-compose up`).

```bash
# Install locust (if not using Docker venv)
pip install locust

# Headless — 50 users, 60 seconds
locust -f load_tests/locustfile.py --headless \
  -u 50 -r 10 --run-time 60s \
  --host http://localhost:8000 \
  --html load_tests/report.html
```

### Expected Results (50 concurrent users, 60 seconds)

| Endpoint | Avg (ms) | p95 (ms) | p99 (ms) | Target |
|----------|----------|----------|----------|--------|
| `/api/analytics/summary` | < 20 | < 50 | < 200 | < 2000 ms |
| `/api/analytics/repeat-customers/revenue` | < 20 | < 50 | < 200 | < 2000 ms |
| `/api/analytics/revenue-trends (daily)` | < 30 | < 100 | < 300 | < 2000 ms |
| `/api/analytics/revenue-trends (monthly)` | < 20 | < 50 | < 200 | < 2000 ms |
| `/api/analytics/top-customers` | < 20 | < 50 | < 200 | < 2000 ms |

> **Note:** Paste your actual Locust terminal output or `load_tests/report.html` screenshot below after running the test.

### Actual Results (fill after running)

```
[Paste Locust summary table here]

Example format:
Endpoint                                           Avg(ms)    p95(ms)    p99(ms)    Reqs    Fails
/api/analytics/summary                             12         35         89         450     0
...
```

**Pass criteria:** All analytics endpoints respond in **< 2 seconds at p99** under 50 concurrent users.

---

## 6. Loom Video (Mandatory)

Record a **Loom** or screen recording with **your face and screen visible** throughout.

### Suggested Video Outline (~8–12 minutes)

1. **Introduction (1 min)**  
   - Your name, project title, GitHub repo link

2. **Architecture Walkthrough (2–3 min)**  
   - Show architecture diagram (README or SUBMISSION.md)  
   - Explain data flow: generator → PostgreSQL → mock APIs → ingestion → analytics

3. **Database Design (2 min)**  
   - Show `models.py` or ER diagram  
   - Explain indexes and materialized views (`database.py`, `generate_data.py`)

4. **API Demo (2–3 min)**  
   - Open http://localhost:8000/docs  
   - Hit `/health`, `/api/analytics/summary`, `/api/analytics/top-customers`  
   - Optionally trigger `/api/ingest/start` and show status

5. **Performance & Optimization (2 min)**  
   - Explain materialized views + Redis cache  
   - Show load test running or results (`load_tests/report.html`)

6. **Code Quality & Scalability (1 min)**  
   - Brief tour: `routers/`, `services/`, Docker setup

7. **Closing (30 sec)**  
   - Recap key decisions, thank reviewer

### Loom Link (paste here after recording)

```
[Loom video URL]
```

---

## 7. Submission Checklist

- [x] GitHub repository pushed: https://github.com/pranjalgautam919/task
- [x] Setup instructions (this document + README.md)
- [x] API documentation (Swagger at `/docs` + tables above)
- [x] Architecture & optimization explanation (Section 4)
- [ ] Load test results (run Locust and paste in Section 5)
- [ ] Loom video recorded and link shared (Section 6)

---

## 8. Evaluation Criteria Mapping

| Criteria | How This Project Addresses It |
|----------|-------------------------------|
| **Backend architecture** | Layered FastAPI app; async I/O; ingestion pipeline; lifespan management |
| **Database design** | Normalized schema, FK constraints, strategic indexes, materialized views |
| **API design** | RESTful endpoints, pagination, Pydantic validation, OpenAPI docs |
| **Performance optimization** | MVs, Redis cache, COPY bulk load, batch inserts, connection pooling |
| **Scalability** | Multi-worker API, Redis shared state, concurrent ingestion, idempotent writes |
| **Code quality** | Modular structure, type hints, logging, Docker, `.gitignore` for secrets |
