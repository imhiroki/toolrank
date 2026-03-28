"""
ToolRank Score Backfill v2
Populates the `scores` table by re-fetching tool definitions from Smithery
for servers already in Supabase. No local JSON needed.

Usage:
  python backfill_scores.py
"""

import json
import time
import sys
import os
import logging
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

SCORING_DIR = os.path.join(os.path.dirname(__file__), "..", "scoring")
sys.path.insert(0, SCORING_DIR)
from toolrank_score import score_server, to_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("backfill")

SMITHERY_BASE = "https://registry.smithery.ai"
BASE_DELAY = 2.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 3.0


def fetch_with_retry(client, url):
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.get(url)
            if resp.status_code == 429:
                wait = max(int(resp.headers.get("Retry-After", 10)), BASE_DELAY * (BACKOFF_FACTOR ** attempt))
                log.warning(f"429 - waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(BASE_DELAY)
                continue
            return None
    return None


def run():
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

    db = create_client(url, key)
    http = httpx.Client(timeout=30)

    # 1. Get all servers from Supabase
    log.info("Fetching servers from Supabase...")
    all_servers = []
    offset = 0
    while True:
        resp = db.table("servers").select("id, server_name, raw_data").range(offset, offset + 999).execute()
        if not resp.data:
            break
        all_servers.extend(resp.data)
        if len(resp.data) < 1000:
            break
        offset += 1000

    log.info(f"Found {len(all_servers)} servers in Supabase")

    # 2. Check which already have scores
    existing = set()
    offset = 0
    while True:
        resp = db.table("scores").select("server_id").range(offset, offset + 999).execute()
        if not resp.data:
            break
        existing.update(r["server_id"] for r in resp.data)
        if len(resp.data) < 1000:
            break
        offset += 1000

    need_scores = [s for s in all_servers if s["id"] not in existing]
    log.info(f"Need scores: {len(need_scores)} (already have: {len(existing)})")

    if not need_scores:
        log.info("All servers already have scores.")
        return

    # 3. For each, fetch from Smithery, score, insert
    scored = 0
    skipped = 0
    errors = 0

    for i, srv in enumerate(need_scores):
        qname = ""
        raw = srv.get("raw_data") or {}
        if isinstance(raw, dict):
            qname = raw.get("qualifiedName", "")
        if not qname:
            qname = srv["server_name"]

        detail = fetch_with_retry(http, f"{SMITHERY_BASE}/servers/{qname}")
        if not detail:
            skipped += 1
            time.sleep(BASE_DELAY)
            continue

        tools = detail.get("tools", [])
        if not tools:
            skipped += 1
            time.sleep(BASE_DELAY)
            continue

        try:
            result = score_server(qname, tools)
            score_dict = to_json(result)

            tools_data = score_dict.get("tools", [])
            if tools_data:
                f_avg = sum(t["dimensions"]["findability"] for t in tools_data) / len(tools_data)
                c_avg = sum(t["dimensions"]["clarity"] for t in tools_data) / len(tools_data)
                p_avg = sum(t["dimensions"]["precision"] for t in tools_data) / len(tools_data)
                e_avg = sum(t["dimensions"]["efficiency"] for t in tools_data) / len(tools_data)
            else:
                f_avg = c_avg = p_avg = e_avg = 0

            total = score_dict.get("average_score", 0)
            if total >= 85: level, level_name = 4, "Dominant"
            elif total >= 70: level, level_name = 3, "Preferred"
            elif total >= 50: level, level_name = 2, "Selectable"
            elif total >= 25: level, level_name = 1, "Visible"
            else: level, level_name = 0, "Absent"

            db.table("scores").insert({
                "server_id": srv["id"],
                "findability": round(f_avg, 1),
                "clarity": round(c_avg, 1),
                "precision": round(p_avg, 1),
                "efficiency": round(e_avg, 1),
                "total_score": round(total, 1),
                "level": level,
                "level_name": level_name,
                "scoring_level": "A",
            }).execute()

            scored += 1
        except Exception as e:
            log.error(f"Error for {qname}: {e}")
            errors += 1

        if (i + 1) % 50 == 0:
            log.info(f"Progress: {i+1}/{len(need_scores)} ({scored} scored, {skipped} skipped)")

        time.sleep(BASE_DELAY)

    log.info(f"Done. Scored: {scored}, Skipped: {skipped}, Errors: {errors}")
    http.close()


if __name__ == "__main__":
    run()
