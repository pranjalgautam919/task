"""
Locust load test for analytics endpoints.

Tests all analytics endpoints under concurrent load to verify
response times remain below 2 seconds.

Usage:
    # Headless mode (for CI/CD):
    locust -f load_tests/locustfile.py --headless -u 50 -r 10 --run-time 60s \
        --host http://localhost:8000 --html load_tests/report.html

    # Web UI mode:
    locust -f load_tests/locustfile.py --host http://localhost:8000
"""

from locust import HttpUser, task, between, events
import time
import json


class AnalyticsUser(HttpUser):
    """Simulates a user hitting analytics endpoints."""

    # Wait 0.5-2 seconds between requests
    wait_time = between(0.5, 2)

    @task(5)
    def get_summary(self):
        """Hit the analytics summary endpoint (most common)."""
        with self.client.get(
            "/api/analytics/summary",
            name="/api/analytics/summary",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("total_orders", 0) > 0:
                    response.success()
                else:
                    response.failure("Empty summary data")
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def get_repeat_customer_revenue(self):
        """Hit the repeat customer revenue endpoint."""
        with self.client.get(
            "/api/analytics/repeat-customers/revenue",
            name="/api/analytics/repeat-customers/revenue",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def get_revenue_trends_daily(self):
        """Hit the daily revenue trends endpoint."""
        with self.client.get(
            "/api/analytics/revenue-trends?period=daily",
            name="/api/analytics/revenue-trends (daily)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def get_revenue_trends_monthly(self):
        """Hit the monthly revenue trends endpoint."""
        with self.client.get(
            "/api/analytics/revenue-trends?period=monthly",
            name="/api/analytics/revenue-trends (monthly)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def get_top_customers(self):
        """Hit the top customers endpoint."""
        with self.client.get(
            "/api/analytics/top-customers?limit=10",
            name="/api/analytics/top-customers",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def get_top_customers_50(self):
        """Hit top customers with larger limit."""
        with self.client.get(
            "/api/analytics/top-customers?limit=50",
            name="/api/analytics/top-customers (top 50)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() > 2:
                response.failure(
                    f"Response too slow: {response.elapsed.total_seconds():.2f}s"
                )
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def health_check(self):
        """Hit health endpoint."""
        self.client.get("/health", name="/health")


class MockAPIUser(HttpUser):
    """Simulates a user hitting mock API endpoints (lower weight)."""

    wait_time = between(1, 3)
    weight = 1  # Lower weight - fewer of these users

    @task(3)
    def get_customers_page(self):
        """Fetch a page of customers."""
        self.client.get(
            "/api/mock/customers?page=1&page_size=100",
            name="/api/mock/customers",
        )

    @task(3)
    def get_orders_page(self):
        """Fetch a page of orders."""
        self.client.get(
            "/api/mock/orders?page=1&page_size=100",
            name="/api/mock/orders",
        )

    @task(2)
    def get_refunds_page(self):
        """Fetch a page of refunds."""
        self.client.get(
            "/api/mock/refunds?page=1&page_size=100",
            name="/api/mock/refunds",
        )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary statistics when test completes."""
    stats = environment.stats
    print("\n" + "=" * 80)
    print("  LOAD TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Endpoint':<50} {'Avg(ms)':<10} {'p50(ms)':<10} {'p95(ms)':<10} {'p99(ms)':<10} {'Reqs':<8} {'Fails':<8}")
    print("-" * 80)

    for name, entry in sorted(stats.entries.items()):
        stat = entry
        print(
            f"{stat.name:<50} "
            f"{stat.avg_response_time:<10.0f} "
            f"{stat.get_response_time_percentile(0.50) or 0:<10.0f} "
            f"{stat.get_response_time_percentile(0.95) or 0:<10.0f} "
            f"{stat.get_response_time_percentile(0.99) or 0:<10.0f} "
            f"{stat.num_requests:<8} "
            f"{stat.num_failures:<8}"
        )

    total = stats.total
    print("-" * 80)
    print(
        f"{'TOTAL':<50} "
        f"{total.avg_response_time:<10.0f} "
        f"{(total.get_response_time_percentile(0.50) or 0):<10.0f} "
        f"{(total.get_response_time_percentile(0.95) or 0):<10.0f} "
        f"{(total.get_response_time_percentile(0.99) or 0):<10.0f} "
        f"{total.num_requests:<8} "
        f"{total.num_failures:<8}"
    )
    print("=" * 80)

    # Check if all endpoints meet the 2s requirement
    all_passed = True
    for name, entry in stats.entries.items():
        p99 = entry.get_response_time_percentile(0.99) or 0
        if p99 > 2000:
            print(f"⚠ FAIL: {entry.name} p99={p99:.0f}ms exceeds 2000ms")
            all_passed = False

    if all_passed:
        print("\n✓ ALL ENDPOINTS MEET THE <2s REQUIREMENT (p99)")
    else:
        print("\n✗ SOME ENDPOINTS EXCEED THE 2s REQUIREMENT")
