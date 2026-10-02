"""Send normal or drifted customers to the local churn API."""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:8000/predict"

CATEGORIES = {
    "gender": ["F", "M"],
    "region": ["Lima", "Norte", "Sur", "Centro"],
    "customer_segment": ["Mass", "Premium"],
    "contract_type": ["Monthly", "Annual"],
    "internet_service": ["Fiber", "DSL"],
    "tv_service": ["Yes", "No"],
    "streaming_service": ["Yes", "No"],
    "payment_method": ["Credit Card", "Bank Transfer"],
}

# mean, std, minimum, maximum
SCENARIOS = {
    "normal": {
        "monthly_fee": (79.0, 12.0, 40.0, 160.0),
        "support_calls": (1.5, 1.0, 0.0, 8.0),
        "last_payment_delay": (2.7, 2.0, 0.0, 14.0),
        "digital_usage_score": (8.2, 1.2, 1.0, 10.0),
    },
    "drift": {
        "monthly_fee": (134.0, 15.0, 80.0, 200.0),
        "support_calls": (5.8, 1.5, 2.0, 12.0),
        "last_payment_delay": (28.0, 6.0, 16.0, 60.0),
        "digital_usage_score": (3.2, 1.0, 1.0, 6.0),
    },
}


def clipped_gauss(mean: float, std: float, minimum: float, maximum: float) -> float:
    value = random.gauss(mean, std)
    return max(minimum, min(maximum, value))


def build_customer(scenario: str, index: int) -> dict:
    profile = SCENARIOS[scenario]
    monthly_fee = clipped_gauss(*profile["monthly_fee"])
    payload = {
        "customer_id": f"NT-SIM-{index:05d}",
        "age": round(clipped_gauss(40, 10, 18, 80), 1),
        "tenure_months": int(clipped_gauss(18, 8, 0, 72)),
        "monthly_fee": round(monthly_fee, 2),
        "total_spent": round(monthly_fee * 12, 2),
        "support_calls": round(clipped_gauss(*profile["support_calls"])),
        "complaints": round(clipped_gauss(1, 1, 0, 6)),
        "last_payment_delay": round(
            clipped_gauss(*profile["last_payment_delay"])
        ),
        "digital_usage_score": round(
            clipped_gauss(*profile["digital_usage_score"]),
            2,
        ),
        "marketing_score": round(clipped_gauss(50, 15, 0, 100), 1),
        "preferred_contact_hour": random.randint(8, 20),
    }
    for field, options in CATEGORIES.items():
        payload[field] = random.choice(options)
    return payload


def post_customer(url: str, payload: dict) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Prediction failed with status {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Prediction failed: {exc.code} {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate operational traffic against the churn API."
    )
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="normal")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    random.seed(args.seed)
    for index in range(args.requests):
        post_customer(args.url, build_customer(args.scenario, index))
        if args.delay:
            time.sleep(args.delay)

    print(f"{args.requests} predictions completed ({args.scenario})")


if __name__ == "__main__":
    main()
