"""
Seeded data generator for Customers, Orders, and Refunds.

Uses Faker with a fixed seed (default: 42) for reproducibility.
Generates data in batches to manage memory efficiently.
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Generator
from faker import Faker

from app.config import get_settings

settings = get_settings()

# Order statuses with weighted distribution
ORDER_STATUSES = ["completed", "completed", "completed", "completed",
                  "processing", "shipped", "cancelled"]

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


def _create_faker(seed: int) -> Faker:
    """Create a seeded Faker instance."""
    fake = Faker()
    Faker.seed(seed)
    return fake


def generate_customers(
    count: int = None,
    seed: int = None,
    batch_size: int = 10_000,
) -> Generator[List[Dict], None, None]:
    """
    Generate customer records in batches.

    Yields lists of customer dicts (batch_size each).
    """
    count = count or settings.CUSTOMERS_COUNT
    seed = seed or settings.SEED
    fake = _create_faker(seed)
    rng = random.Random(seed)

    batch = []
    for i in range(count):
        customer = {
            "id": str(uuid.UUID(int=rng.getrandbits(128))),
            "name": fake.name(),
            "email": f"user{i}@{fake.domain_name()}",
            "phone": fake.phone_number(),
            "address": fake.street_address(),
            "city": fake.city(),
            "state": fake.state(),
            "country": fake.country(),
            "zip_code": fake.zipcode(),
            "created_at": fake.date_time_between(
                start_date="-3y", end_date="-1y"
            ).isoformat(),
        }
        batch.append(customer)

        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


def generate_orders(
    customer_ids: List[str],
    count: int = None,
    seed: int = None,
    batch_size: int = 10_000,
) -> Generator[List[Dict], None, None]:
    """
    Generate order records in batches.

    Each order references a random customer.
    Yields lists of order dicts (batch_size each).
    """
    count = count or settings.ORDERS_COUNT
    seed = seed or settings.SEED
    # Use a different seed offset for orders
    rng = random.Random(seed + 1)
    fake = _create_faker(seed + 1)

    batch = []
    for i in range(count):
        order = {
            "id": str(uuid.UUID(int=rng.getrandbits(128))),
            "customer_id": rng.choice(customer_ids),
            "total_amount": round(rng.uniform(5.0, 2000.0), 2),
            "status": rng.choice(ORDER_STATUSES),
            "order_date": fake.date_time_between(
                start_date="-1y", end_date="now"
            ).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        batch.append(order)

        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


def generate_refunds(
    order_ids: List[str],
    count: int = None,
    seed: int = None,
    batch_size: int = 10_000,
) -> Generator[List[Dict], None, None]:
    """
    Generate refund records in batches.

    Each refund references a unique order.
    Yields lists of refund dicts (batch_size each).
    """
    count = count or settings.REFUNDS_COUNT
    seed = seed or settings.SEED
    # Use a different seed offset for refunds
    rng = random.Random(seed + 2)
    fake = _create_faker(seed + 2)

    # Select unique orders for refunds (no duplicate refunds per order)
    if count > len(order_ids):
        count = len(order_ids)
    refund_order_ids = rng.sample(order_ids, count)

    batch = []
    for i, order_id in enumerate(refund_order_ids):
        refund = {
            "id": str(uuid.UUID(int=rng.getrandbits(128))),
            "order_id": order_id,
            "refund_amount": round(rng.uniform(5.0, 500.0), 2),
            "reason": rng.choice(REFUND_REASONS),
            "status": rng.choice(REFUND_STATUSES),
            "refund_date": fake.date_time_between(
                start_date="-6m", end_date="now"
            ).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        batch.append(refund)

        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch
