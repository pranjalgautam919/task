# Loom Video Script — Analytics Backend Service

**Duration:** 8–12 minutes  
**Requirements:** Face + screen visible at all times  
**Repo:** https://github.com/pranjalgautam919/task

---

## Before Recording

1. Start Docker Desktop
2. Run: `docker-compose up --build` (wait until API is ready)
3. Open tabs:
   - GitHub repo
   - http://localhost:8000/docs
   - README.md or SUBMISSION.md (architecture section)
   - VS Code with `app/` folder open
4. Optional: run Locust in a terminal for live demo

---

## Script

### [0:00 – 1:00] Introduction

> "Hi, I'm Pranjal. This is my submission for the Analytics Backend Service assignment.
>
> I built a high-performance FastAPI backend that handles 1.3 million e-commerce records and serves analytics APIs with response times under 2 seconds.
>
> The code is on GitHub at github.com/pranjalgautam919/task."

*[Show GitHub repo on screen]*

---

### [1:00 – 3:30] Architecture

> "Let me walk through the architecture."

*[Open README or SUBMISSION.md architecture diagram]*

> "The system has five main layers:
>
> 1. **Data Generator** — uses Faker with seed 42 to create 100K customers, 1M orders, and 200K refunds. Data is bulk-loaded into PostgreSQL using the COPY protocol for speed.
>
> 2. **Mock APIs** — paginated REST endpoints that simulate an external data source.
>
> 3. **Ingestion Service** — an async pipeline using httpx that pulls all pages concurrently and batch-inserts into PostgreSQL. It's idempotent using ON CONFLICT DO NOTHING.
>
> 4. **Materialized Views** — pre-aggregated analytics data so we don't scan 1 million rows on every request.
>
> 5. **Redis Cache** — 60-second TTL on analytics responses for sub-10ms repeat queries.
>
> The analytics APIs read from materialized views first, then cache, giving us consistent sub-second responses."

---

### [3:30 – 5:30] Database Design

*[Open `app/models.py` or `scripts/generate_data.py`]*

> "Database design uses three normalized tables: customers, orders, and refunds with foreign key constraints.
>
> I added strategic indexes — on customer_id, order_date, status, and composite indexes on (customer_id, total_amount) for top-customer queries.
>
> The key optimization is three materialized views:"

*[Open `app/database.py` — scroll to MV definitions]*

> "- `mv_analytics_summary` — single row with all KPIs
> - `mv_customer_spend` — per-customer aggregation for top customers and repeat revenue
> - `mv_daily_revenue` — daily trends
>
> These are refreshed after ingestion using REFRESH MATERIALIZED VIEW CONCURRENTLY where possible."

---

### [5:30 – 8:00] API Demo

*[Open http://localhost:8000/docs]*

> "All APIs are documented with Swagger UI."

**Demo each:**

1. `GET /health` — "Checks PostgreSQL and Redis connectivity"
2. `GET /api/analytics/summary` — "Returns total orders, revenue, refunds, net revenue, and average order value"
3. `GET /api/analytics/top-customers?limit=5` — "Top customers by spend from materialized view"
4. `GET /api/analytics/revenue-trends?period=monthly` — "Monthly revenue trends"
5. `GET /api/mock/customers?page=1&page_size=5` — "Paginated mock data source"

**Optional ingestion demo:**

> "POST /api/ingest/start triggers the full pipeline — fetches from mock APIs, inserts in batches, refreshes views, and clears cache. Status is tracked in Redis so it works across multiple workers."

*[Trigger ingest/start, show ingest/status]*

---

### [8:00 – 10:00] Performance & Load Testing

*[Open terminal or `load_tests/locustfile.py`]*

> "For performance validation I used Locust with 50 concurrent users for 60 seconds."

```bash
locust -f load_tests/locustfile.py --headless -u 50 -r 10 --run-time 60s --host http://localhost:8000
```

> "All analytics endpoints stay well under 2 seconds at p99 because:
> - Materialized views avoid full table scans
> - Redis caches repeat queries
> - Indexes speed up JOINs and filters
> - Async I/O handles concurrency efficiently"

*[Show Locust results table or report.html]*

---

### [10:00 – 11:30] Code Quality & Scalability

*[Open VS Code — project structure]*

> "Code is organized into routers, services, and database layers.
>
> Scalability decisions:
> - Uvicorn runs 4 workers
> - Ingestion status in Redis, not in-memory
> - Connection pooling with 20+10 overflow connections
> - Batch processing keeps memory usage controlled
> - Docker Compose gives one-command deployment"

*[Briefly show `docker-compose.yml`]*

---

### [11:30 – 12:00] Closing

> "To summarize: I focused on backend architecture with clear separation of concerns, a well-indexed database with materialized views, RESTful APIs with full documentation, and multiple performance layers to hit the sub-2-second target at scale.
>
> Setup is one command: docker-compose up --build.
>
> Thank you for reviewing my submission. The repo link and full documentation are in SUBMISSION.md."

---

## After Recording

1. Upload to [Loom](https://www.loom.com)
2. Paste Loom link in SUBMISSION.md (Section 6)
3. Share with evaluator along with repo link
