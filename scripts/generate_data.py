"""
Data generation script — seeds PostgreSQL with reproducible test data.

Generates:
- 100,000 Customers
- 1,000,000 Orders
- 200,000 Refunds

Uses synchronous psycopg2 with COPY protocol for maximum insert speed.
All data is generated with seed=42 for reproducibility.
"""

import os
import sys
import time
import uuid
import random
import io
import csv
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker


# ─── Configuration ───────────────────────────────────────────────────────────

SEED = int(os.getenv("SEED", "42"))
DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://postgres:postgres@db:5432/analytics_db",
)

CUSTOMERS_COUNT = int(os.getenv("CUSTOMERS_COUNT", "100000"))
ORDERS_COUNT = int(os.getenv("ORDERS_COUNT", "1000000"))
REFUNDS_COUNT = int(os.getenv("REFUNDS_COUNT", "200000"))

ORDER_STATUSES = [
    "completed", "completed", "completed", "completed",
    "processing", "shipped", "cancelled",
]

REFUND_REASONS = [
    "Product not as described",
    "Damaged during shipping",
    "Wrong item received",
    "Changed mind",
    "Late delivery",
    "Quality issues",
    "Duplicate order",
    "Better price elsewhere",
]

REFUND_STATUSES = ["completed", "completed", "completed", "pending", "rejected"]


def get_connection():
    """Get PostgreSQL connection with retry."""
    max_retries = 10
    retry_delay = 3

    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            return conn
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"  DB connection attempt {attempt + 1}/{max_retries} failed: {e}")
                print(f"  Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise


def create_tables(conn):
    """Create tables if they don't exist."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(50),
            address VARCHAR(500),
            city VARCHAR(100),
            state VARCHAR(100),
            country VARCHAR(100),
            zip_code VARCHAR(20),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id UUID PRIMARY KEY,
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            total_amount FLOAT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'completed',
            order_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS refunds (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
            refund_amount FLOAT NOT NULL,
            reason VARCHAR(500),
            status VARCHAR(50) NOT NULL DEFAULT 'completed',
            refund_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    # Create indexes
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders (customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);",
        "CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders (order_date);",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_amount ON orders (customer_id, total_amount);",
        "CREATE INDEX IF NOT EXISTS idx_orders_status_amount ON orders (status, total_amount);",
        "CREATE INDEX IF NOT EXISTS idx_refunds_order_id ON refunds (order_id);",
        "CREATE INDEX IF NOT EXISTS idx_refunds_status ON refunds (status);",
        "CREATE INDEX IF NOT EXISTS idx_refunds_status_amount ON refunds (status, refund_amount);",
    ]

    for stmt in index_statements:
        cur.execute(stmt)

    conn.commit()
    cur.close()
    print("✓ Tables and indexes created")


def check_data_exists(conn):
    """Check if data already exists in the database."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers;")
    count = cur.fetchone()[0]
    cur.close()
    return count > 0


def generate_and_insert_customers(conn):
    """Generate and bulk insert customers using COPY."""
    print(f"\n{'='*60}")
    print(f"Generating {CUSTOMERS_COUNT:,} customers...")
    start = time.time()

    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)

    cur = conn.cursor()

    # Generate CSV data in memory for COPY
    batch_size = 10_000
    customer_ids = []
    total_inserted = 0

    for batch_start in range(0, CUSTOMERS_COUNT, batch_size):
        batch_end = min(batch_start + batch_size, CUSTOMERS_COUNT)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)

        for i in range(batch_start, batch_end):
            cid = str(uuid.UUID(int=rng.getrandbits(128)))
            customer_ids.append(cid)
            writer.writerow([
                cid,
                fake.name().replace('\t', ' '),
                f"user{i}@{fake.domain_name()}",
                fake.phone_number(),
                fake.street_address().replace('\t', ' '),
                fake.city(),
                fake.state(),
                fake.country().replace('\t', ' '),
                fake.zipcode(),
                fake.date_time_between(start_date="-3y", end_date="-1y").isoformat(),
            ])

        buffer.seek(0)
        cur.copy_from(
            buffer, 'customers',
            sep='\t',
            columns=(
                'id', 'name', 'email', 'phone', 'address',
                'city', 'state', 'country', 'zip_code', 'created_at',
            ),
        )
        conn.commit()
        total_inserted += (batch_end - batch_start)
        elapsed = time.time() - start
        print(f"  Customers: {total_inserted:>8,} / {CUSTOMERS_COUNT:,} "
              f"({total_inserted*100//CUSTOMERS_COUNT}%) - {elapsed:.1f}s")

    cur.close()
    elapsed = time.time() - start
    print(f"✓ {CUSTOMERS_COUNT:,} customers inserted in {elapsed:.1f}s")
    return customer_ids


def generate_and_insert_orders(conn, customer_ids):
    """Generate and bulk insert orders using COPY."""
    print(f"\n{'='*60}")
    print(f"Generating {ORDERS_COUNT:,} orders...")
    start = time.time()

    rng = random.Random(SEED + 1)
    fake = Faker()
    Faker.seed(SEED + 1)

    cur = conn.cursor()
    batch_size = 50_000
    order_ids = []
    total_inserted = 0

    for batch_start in range(0, ORDERS_COUNT, batch_size):
        batch_end = min(batch_start + batch_size, ORDERS_COUNT)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)

        for i in range(batch_start, batch_end):
            oid = str(uuid.UUID(int=rng.getrandbits(128)))
            order_ids.append(oid)
            writer.writerow([
                oid,
                rng.choice(customer_ids),
                round(rng.uniform(5.0, 2000.0), 2),
                rng.choice(ORDER_STATUSES),
                fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
                datetime.utcnow().isoformat(),
            ])

        buffer.seek(0)
        cur.copy_from(
            buffer, 'orders',
            sep='\t',
            columns=(
                'id', 'customer_id', 'total_amount',
                'status', 'order_date', 'created_at',
            ),
        )
        conn.commit()
        total_inserted += (batch_end - batch_start)
        elapsed = time.time() - start
        print(f"  Orders: {total_inserted:>10,} / {ORDERS_COUNT:,} "
              f"({total_inserted*100//ORDERS_COUNT}%) - {elapsed:.1f}s")

    cur.close()
    elapsed = time.time() - start
    print(f"✓ {ORDERS_COUNT:,} orders inserted in {elapsed:.1f}s")
    return order_ids


def generate_and_insert_refunds(conn, order_ids):
    """Generate and bulk insert refunds using COPY."""
    print(f"\n{'='*60}")
    print(f"Generating {REFUNDS_COUNT:,} refunds...")
    start = time.time()

    rng = random.Random(SEED + 2)
    fake = Faker()
    Faker.seed(SEED + 2)

    # Select unique orders for refunds
    refund_order_ids = rng.sample(order_ids, REFUNDS_COUNT)

    cur = conn.cursor()
    batch_size = 10_000
    total_inserted = 0

    for batch_start in range(0, REFUNDS_COUNT, batch_size):
        batch_end = min(batch_start + batch_size, REFUNDS_COUNT)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)

        for i in range(batch_start, batch_end):
            writer.writerow([
                str(uuid.UUID(int=rng.getrandbits(128))),
                refund_order_ids[i],
                round(rng.uniform(5.0, 500.0), 2),
                rng.choice(REFUND_REASONS),
                rng.choice(REFUND_STATUSES),
                fake.date_time_between(start_date="-6m", end_date="now").isoformat(),
                datetime.utcnow().isoformat(),
            ])

        buffer.seek(0)
        cur.copy_from(
            buffer, 'refunds',
            sep='\t',
            columns=(
                'id', 'order_id', 'refund_amount',
                'reason', 'status', 'refund_date', 'created_at',
            ),
        )
        conn.commit()
        total_inserted += (batch_end - batch_start)
        elapsed = time.time() - start
        print(f"  Refunds: {total_inserted:>8,} / {REFUNDS_COUNT:,} "
              f"({total_inserted*100//REFUNDS_COUNT}%) - {elapsed:.1f}s")

    cur.close()
    elapsed = time.time() - start
    print(f"✓ {REFUNDS_COUNT:,} refunds inserted in {elapsed:.1f}s")


def create_materialized_views(conn):
    """Create materialized views for analytics performance."""
    print(f"\n{'='*60}")
    print("Creating materialized views...")
    start = time.time()
    cur = conn.cursor()

    # Daily revenue materialized view
    cur.execute("""
        DROP MATERIALIZED VIEW IF EXISTS mv_analytics_summary CASCADE;
    """)
    cur.execute("""
        DROP MATERIALIZED VIEW IF EXISTS mv_customer_spend CASCADE;
    """)
    cur.execute("""
        DROP MATERIALIZED VIEW IF EXISTS mv_daily_revenue CASCADE;
    """)
    conn.commit()

    cur.execute("""
        CREATE MATERIALIZED VIEW mv_daily_revenue AS
        SELECT
            DATE(order_date) AS order_day,
            COUNT(*) AS order_count,
            COALESCE(SUM(total_amount), 0) AS daily_revenue
        FROM orders
        WHERE status != 'cancelled'
        GROUP BY DATE(order_date)
        ORDER BY order_day;
    """)
    conn.commit()
    print("  ✓ mv_daily_revenue created")

    # Customer spend materialized view
    cur.execute("""
        CREATE MATERIALIZED VIEW mv_customer_spend AS
        SELECT
            o.customer_id,
            c.name AS customer_name,
            c.email AS customer_email,
            COUNT(o.id) AS total_orders,
            COALESCE(SUM(o.total_amount), 0) AS total_spend
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.status != 'cancelled'
        GROUP BY o.customer_id, c.name, c.email;
    """)
    conn.commit()
    print("  ✓ mv_customer_spend created")

    # Analytics summary materialized view (single row)
    cur.execute("""
        CREATE MATERIALIZED VIEW mv_analytics_summary AS
        SELECT
            (SELECT COUNT(*) FROM orders WHERE status != 'cancelled') AS total_orders,
            (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled') AS total_revenue,
            (SELECT COUNT(*) FROM refunds WHERE status = 'completed') AS total_refunds,
            (SELECT COALESCE(SUM(refund_amount), 0) FROM refunds WHERE status = 'completed') AS total_refund_amount,
            (
                (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled')
                -
                (SELECT COALESCE(SUM(refund_amount), 0) FROM refunds WHERE status = 'completed')
            ) AS net_revenue,
            (
                (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled')
                /
                NULLIF((SELECT COUNT(*) FROM orders WHERE status != 'cancelled'), 0)
            ) AS avg_order_value;
    """)
    conn.commit()
    print("  ✓ mv_analytics_summary created")

    # Create indexes on materialized views
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_revenue_day
        ON mv_daily_revenue (order_day);
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_customer_spend_id
        ON mv_customer_spend (customer_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_customer_spend_total
        ON mv_customer_spend (total_spend DESC);
    """)
    conn.commit()
    print("  ✓ Materialized view indexes created")

    cur.close()
    elapsed = time.time() - start
    print(f"✓ All materialized views created in {elapsed:.1f}s")


def main():
    """Main entry point for data generation."""
    print("=" * 60)
    print("  ANALYTICS DATA GENERATOR")
    print(f"  Seed: {SEED}")
    print(f"  Customers: {CUSTOMERS_COUNT:,}")
    print(f"  Orders:    {ORDERS_COUNT:,}")
    print(f"  Refunds:   {REFUNDS_COUNT:,}")
    print("=" * 60)

    total_start = time.time()

    # Connect to database
    print("\nConnecting to database...")
    conn = get_connection()
    print("✓ Connected to database")

    # Create tables
    create_tables(conn)

    # Check if data already exists
    if check_data_exists(conn):
        print("\n⚠ Data already exists in database. Skipping generation.")
        print("  To regenerate, drop the tables first or use a fresh database.")
        # Still recreate materialized views in case they're missing
        create_materialized_views(conn)
        conn.close()
        return

    # Generate and insert data
    customer_ids = generate_and_insert_customers(conn)
    order_ids = generate_and_insert_orders(conn, customer_ids)
    generate_and_insert_refunds(conn, order_ids)

    # Create materialized views
    create_materialized_views(conn)

    conn.close()

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  COMPLETE — Total time: {total_elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
