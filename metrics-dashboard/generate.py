#!/usr/bin/env python3
"""Generate static dashboard data from the metrics database."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.metrics import get_metrics_summary, get_metrics_timeseries, get_recent_metrics

def main():
    db = os.environ.get("CASHEW_DB", "data/graph.db")
    out = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out, exist_ok=True)

    hours = int(os.environ.get("CASHEW_METRICS_HOURS", "720"))

    summary = get_metrics_summary(db, hours=hours)
    timeseries = get_metrics_timeseries(db, "retrieval", hours=hours)
    recent = get_recent_metrics(db, limit=50)

    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    with open(os.path.join(out, "timeseries.json"), "w") as f:
        json.dump(timeseries, f, indent=2, default=str)
    with open(os.path.join(out, "recent.json"), "w") as f:
        json.dump(recent, f, indent=2, default=str)

    print(f"Generated: {summary['total_queries']} queries, {len(timeseries)} timeseries, {len(recent)} recent")

if __name__ == "__main__":
    main()
