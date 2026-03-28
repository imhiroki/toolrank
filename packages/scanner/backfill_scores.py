"""
ToolRank Score Backfill
Populates the `scores` table from existing scan data in `servers` table.
Run once after fixing the scanner to also write scores.

Usage:
  python backfill_scores.py               # Backfill from local JSON data
  python backfill_scores.py --from-db     # Backfill using server IDs already in Supabase
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("backfill")

DATA_DIR = Path(__file__).parent / "data"


def run():
    parser = argparse.ArgumentParser(description="Backfill scores table")
    parser.add_argument("--from-db", action="store_true", help="Fetch server IDs from Supabase")
    args = parser.parse_args()

    try:
        from supabase import create_client
    except ImportError:
        print("pip install supabase")
        sys.exit(1)

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return

    client = create_client(url, key)

    # Load local scan data
    scores_file = DATA_DIR / "latest_scores.json"
    if not scores_file.exists():
        log.error(f"No local data at {scores_file}. Run scanner first or download from GitHub Actions artifacts.")
        return

    with open(scores_file) as f:
        results = json.load(f)

    log.info(f"Loaded {len(results)} results from local data")

    # Build lookup: server_name -> score data
    score_lookup = {}
    for r in results:
        tools = r.get("tools", [])
        if tools:
            f_avg = sum(t["dimensions"]["findability"] for t in tools) / len(tools)
            c_avg = sum(t["dimensions"]["clarity"] for t in tools) / len(tools)
            p_avg = sum(t["dimensions"]["precision"] for t in tools) / len(tools)
            e_avg = sum(t["dimensions"]["efficiency"] for t in tools) / len(tools)
        else:
            f_avg = c_avg = p_avg = e_avg = 0

        total = r.get("average_score", 0)
        if total >= 85: level, level_name = 4, "Dominant"
        elif total >= 70: level, level_name = 3, "Preferred"
        elif total >= 50: level, level_name = 2, "Selectable"
        elif total >= 25: level, level_name = 1, "Visible"
        else: level, level_name = 0, "Absent"

        score_lookup[r["server_name"]] = {
            "findability": round(f_avg, 1),
            "clarity": round(c_avg, 1),
            "precision": round(p_avg, 1),
            "efficiency": round(e_avg, 1),
            "total_score": round(total, 1),
            "level": level,
            "level_name": level_name,
            "scoring_level": "A",
        }

    # Fetch all server IDs from Supabase
    log.info("Fetching server IDs from Supabase...")
    all_servers = []
    offset = 0
    batch_size = 1000
    while True:
        resp = client.table("servers").select("id, server_name").range(offset, offset + batch_size - 1).execute()
        if not resp.data:
            break
        all_servers.extend(resp.data)
        if len(resp.data) < batch_size:
            break
        offset += batch_size

    log.info(f"Found {len(all_servers)} servers in Supabase")

    # Match and insert scores
    inserted = 0
    skipped = 0
    for srv in all_servers:
        name = srv["server_name"]
        if name not in score_lookup:
            skipped += 1
            continue

        score_data = {
            "server_id": srv["id"],
            **score_lookup[name],
        }

        try:
            client.table("scores").insert(score_data).execute()
            inserted += 1
        except Exception as e:
            log.error(f"Insert error for {name}: {e}")

        if inserted % 100 == 0 and inserted > 0:
            log.info(f"Progress: {inserted} inserted")

    log.info(f"Done. Inserted: {inserted}, Skipped: {skipped} (no score data)")


if __name__ == "__main__":
    run()
