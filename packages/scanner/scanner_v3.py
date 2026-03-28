"""
ToolRank Auto Scanner v0.3
- 2-second interval between requests (respectful to Smithery)
- Weekly full scan (Sunday) / Daily differential scan (Mon-Sat)
- Rate limit handling with exponential backoff
- Fixed Supabase column mapping

Usage:
  python scanner_v3.py --supabase              # Auto: full on Sunday, diff on other days
  python scanner_v3.py --supabase --full        # Force full scan
  python scanner_v3.py --supabase --diff        # Force diff scan
  python scanner_v3.py --limit 10               # Scan first 10 (testing)
  python scanner_v3.py --dry-run                # Preview without saving
"""

import json
import time
import sys
import os
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

SCORING_DIR = Path(__file__).parent.parent / "scoring"
sys.path.insert(0, str(SCORING_DIR))
from toolrank_score import score_server, to_json, format_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("scanner")

SMITHERY_BASE = "https://registry.smithery.ai"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Rate limit config — be a good neighbor
BASE_DELAY = 2.0        # 2 seconds between detail requests
LIST_DELAY = 1.0         # 1 second between list pages
MAX_RETRIES = 3
BACKOFF_FACTOR = 3.0     # aggressive backoff on 429


def fetch_with_retry(client: httpx.Client, url: str, max_retries: int = MAX_RETRIES) -> dict | None:
    """Fetch URL with exponential backoff on rate limit."""
    for attempt in range(max_retries + 1):
        try:
            resp = client.get(url)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                wait = max(retry_after, BASE_DELAY * (BACKOFF_FACTOR ** attempt))
                log.warning(f"Rate limited (429). Waiting {wait:.0f}s (attempt {attempt+1}/{max_retries+1})")
                time.sleep(wait)
                continue

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            return resp.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = BASE_DELAY * (BACKOFF_FACTOR ** attempt)
                log.warning(f"Rate limited. Waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            log.debug(f"HTTP error for {url}: {e}")
            return None
        except Exception as e:
            log.debug(f"Request error for {url}: {e}")
            if attempt < max_retries:
                time.sleep(BASE_DELAY)
                continue
            return None

    log.error(f"Max retries exceeded for {url}")
    return None


def fetch_server_list(client: httpx.Client, page_size: int = 50, max_servers: int = None) -> list[dict]:
    """Fetch all servers from Smithery (paginated)."""
    servers = []
    page = 1

    while True:
        data = fetch_with_retry(
            client,
            f"{SMITHERY_BASE}/servers?pageSize={page_size}&page={page}"
        )
        if not data:
            break

        page_servers = data.get("servers", [])
        if not page_servers:
            break

        servers.extend(page_servers)

        pagination = data.get("pagination", {})
        total = pagination.get("totalCount", 0)
        total_pages = pagination.get("totalPages", 0)

        log.info(f"Page {page}/{total_pages}: +{len(page_servers)} servers (total: {len(servers)}/{total})")

        if max_servers and len(servers) >= max_servers:
            servers = servers[:max_servers]
            break

        if page >= total_pages:
            break

        page += 1
        time.sleep(LIST_DELAY)

    return servers


def load_known_servers() -> set[str]:
    """Load previously scanned server names from local data."""
    latest = DATA_DIR / "latest_scores.json"
    if not latest.exists():
        return set()
    try:
        with open(latest) as f:
            data = json.load(f)
        return {r["server_name"] for r in data}
    except Exception:
        return set()


def save_local(results: list[dict], summary: dict):
    """Save scan results to local JSON files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    scores_file = DATA_DIR / f"scores_{timestamp}.json"
    with open(scores_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info(f"Scores saved: {scores_file}")

    summary_file = DATA_DIR / f"summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log.info(f"Summary saved: {summary_file}")

    # Overwrite latest for easy access & diff comparison
    for name, data in [("latest_scores.json", results), ("latest_summary.json", summary)]:
        with open(DATA_DIR / name, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def save_supabase(results: list[dict], summary: dict):
    """Save scan results to Supabase."""
    try:
        from supabase import create_client
    except ImportError:
        log.error("Install supabase: pip install supabase")
        return

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
        return

    client = create_client(url, key)
    saved = 0

    for result in results:
        try:
            server_data = {
                "source": "smithery",
                "server_name": result["server_name"],
                "display_name": result.get("display_name", result["server_name"]),
                "description": result.get("server_description", ""),
                "tool_count": len(result.get("tools", [])),
                "raw_data": result.get("server_meta", {}),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            client.table("servers").upsert(
                server_data, on_conflict="source,server_name"
            ).execute()
            saved += 1
        except Exception as e:
            log.error(f"Supabase write error for {result['server_name']}: {e}")

    # Save summary — column names match schema.sql exactly
    dist = summary.get("distribution", {})
    try:
        summary_row = {
            "source": "smithery",
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "total_servers": summary.get("total_in_registry", 0),
            "scored_servers": summary.get("scored", 0),
            "errors": summary.get("errors", 0),
            "avg_score": summary.get("average_score", 0),
            "dominant_count": dist.get("dominant_85+", 0),
            "preferred_count": dist.get("preferred_70_84", 0),
            "selectable_count": dist.get("selectable_50_69", 0),
            "visible_count": dist.get("visible_25_49", 0),
            "absent_count": dist.get("absent_0_24", 0),
            "raw_summary": summary,
        }
        client.table("scan_summaries").upsert(
            summary_row, on_conflict="source,scan_date"
        ).execute()
    except Exception as e:
        log.error(f"Supabase summary error: {e}")

    log.info(f"Saved {saved}/{len(results)} servers to Supabase")


def score_single_server(client: httpx.Client, server: dict) -> dict | None:
    """Fetch detail and score a single server. Returns score dict or None."""
    qname = server.get("qualifiedName", "")
    if not qname:
        return None

    detail = fetch_with_retry(client, f"{SMITHERY_BASE}/servers/{qname}")
    if not detail:
        return None

    tools = detail.get("tools", [])
    if not tools:
        return None

    try:
        score_result = score_server(qname, tools)
        score_dict = to_json(score_result)

        score_dict["display_name"] = server.get("displayName", qname)
        score_dict["server_description"] = server.get("description", "")
        score_dict["use_count"] = server.get("useCount", 0)
        score_dict["verified"] = server.get("verified", False)
        score_dict["is_deployed"] = server.get("isDeployed", False)
        score_dict["server_meta"] = {
            "id": server.get("id"),
            "qualifiedName": qname,
            "remote": server.get("remote", False),
            "homepage": server.get("homepage", ""),
        }
        return score_dict
    except Exception as e:
        log.error(f"Scoring error for {qname}: {e}")
        return None


def run_scan(limit: int = None, dry_run: bool = False, use_supabase: bool = False,
             verbose: bool = False, force_full: bool = False, force_diff: bool = False):
    """Main scan orchestrator."""
    client = httpx.Client(timeout=30)

    # Determine scan mode
    is_sunday = datetime.now().weekday() == 6
    if force_full:
        scan_mode = "full"
    elif force_diff:
        scan_mode = "diff"
    elif limit:
        scan_mode = "full"  # limit implies testing
    else:
        scan_mode = "full" if is_sunday else "diff"

    log.info(f"Scan mode: {scan_mode} (Sunday={is_sunday})")

    # Step 1: Get server list (lightweight, just metadata)
    log.info("Step 1: Fetching server list from Smithery...")
    servers = fetch_server_list(client, max_servers=limit)
    log.info(f"Got {len(servers)} servers from registry")

    # Step 2: Determine which servers to scan in detail
    if scan_mode == "diff":
        known = load_known_servers()
        new_servers = [s for s in servers if s.get("qualifiedName", "") not in known]
        log.info(f"Diff mode: {len(new_servers)} new servers (skipping {len(servers) - len(new_servers)} known)")
        targets = new_servers
    else:
        targets = servers

    # Step 3: Fetch details and score
    log.info(f"Step 2: Scoring {len(targets)} servers (interval: {BASE_DELAY}s)...")
    estimated_minutes = len(targets) * BASE_DELAY / 60
    log.info(f"Estimated time: ~{estimated_minutes:.0f} minutes")

    results = []
    scored = 0
    skipped = 0
    errors = 0

    for i, server in enumerate(targets):
        result = score_single_server(client, server)
        if result:
            results.append(result)
            scored += 1
            if verbose:
                print(f"  {result['average_score']:5.1f}  {result['server_name']}")
        else:
            skipped += 1

        if (i + 1) % 50 == 0:
            log.info(f"Progress: {i+1}/{len(targets)} ({scored} scored, {skipped} skipped)")

        time.sleep(BASE_DELAY)

    # For diff mode, merge with existing data
    if scan_mode == "diff":
        latest = DATA_DIR / "latest_scores.json"
        if latest.exists():
            try:
                with open(latest) as f:
                    existing = json.load(f)
                # Merge: new results overwrite existing by server_name
                existing_map = {r["server_name"]: r for r in existing}
                for r in results:
                    existing_map[r["server_name"]] = r
                results = list(existing_map.values())
                log.info(f"Merged: {scored} new + {len(existing)} existing = {len(results)} total")
            except Exception:
                pass

    # Build summary
    avg_score = round(sum(r["average_score"] for r in results) / len(results), 1) if results else 0

    summary = {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scan_mode": scan_mode,
        "total_in_registry": len(servers),
        "scored": scored,
        "skipped": skipped,
        "errors": errors,
        "total_in_db": len(results),
        "average_score": avg_score,
        "distribution": {
            "dominant_85+": len([r for r in results if r["average_score"] >= 85]),
            "preferred_70_84": len([r for r in results if 70 <= r["average_score"] < 85]),
            "selectable_50_69": len([r for r in results if 50 <= r["average_score"] < 70]),
            "visible_25_49": len([r for r in results if 25 <= r["average_score"] < 50]),
            "absent_0_24": len([r for r in results if r["average_score"] < 25]),
        },
        "top_10": sorted(results, key=lambda r: r["average_score"], reverse=True)[:10],
        "bottom_10": sorted(results, key=lambda r: r["average_score"])[:10],
    }

    # Print summary
    print("\n" + "=" * 60)
    print(f"ToolRank Ecosystem Scan Complete ({scan_mode} mode)")
    print(f"=" * 60)
    print(f"Servers in registry: {len(servers)}")
    print(f"Scored this run: {scored} | Skipped: {skipped} | Errors: {errors}")
    print(f"Total in database: {len(results)}")
    print(f"Average ToolRank Score: {avg_score}/100")
    print(f"\nDistribution:")
    for level, count in summary["distribution"].items():
        bar = "█" * (count // max(1, len(results) // 40))
        print(f"  {level:20s}: {count:4d} {bar}")
    print(f"\nTop 5:")
    for r in summary["top_10"][:5]:
        print(f"  {r['average_score']:5.1f}  {r['server_name']} ({r.get('display_name', '')})")
    print(f"\nBottom 5:")
    for r in summary["bottom_10"][:5]:
        print(f"  {r['average_score']:5.1f}  {r['server_name']} ({r.get('display_name', '')})")

    # Save
    if not dry_run:
        save_local(results, summary)
        if use_supabase:
            save_supabase(results, summary)
    else:
        log.info("Dry run — nothing saved")

    client.close()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ToolRank Auto Scanner v0.3")
    parser.add_argument("--limit", type=int, help="Max servers to scan (testing)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save results")
    parser.add_argument("--supabase", action="store_true", help="Save to Supabase")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each score")
    parser.add_argument("--full", action="store_true", help="Force full scan")
    parser.add_argument("--diff", action="store_true", help="Force diff scan")
    args = parser.parse_args()

    run_scan(
        limit=args.limit,
        dry_run=args.dry_run,
        use_supabase=args.supabase,
        verbose=args.verbose,
        force_full=args.full,
        force_diff=args.diff,
    )
