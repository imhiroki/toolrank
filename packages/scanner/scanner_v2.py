"""
ToolRank Auto Scanner v0.2
Updated for verified Smithery API structure (2026-03-28).

Two-step fetch:
  1. GET /servers?pageSize=50 → qualifiedName list
  2. GET /servers/{qualifiedName} → full tool definitions

Usage:
  python scanner_v2.py                     # Full scan, save to local JSON
  python scanner_v2.py --limit 10          # Scan first 10 servers only
  python scanner_v2.py --supabase          # Save to Supabase (requires env vars)
  python scanner_v2.py --dry-run           # Preview without saving
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

# Import scoring engine
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


def fetch_server_list(client: httpx.Client, page_size: int = 50, max_servers: int = None) -> list[dict]:
    """Fetch all servers from Smithery (paginated)."""
    servers = []
    page = 1
    
    while True:
        try:
            resp = client.get(
                f"{SMITHERY_BASE}/servers",
                params={"pageSize": page_size, "page": page}
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error(f"List page {page} failed: {e}")
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
        time.sleep(0.3)
    
    return servers


def fetch_server_detail(client: httpx.Client, qualified_name: str) -> dict | None:
    """Fetch full server detail including tool definitions."""
    try:
        resp = client.get(f"{SMITHERY_BASE}/servers/{qualified_name}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.debug(f"Detail fetch failed for {qualified_name}: {e}")
        return None


def save_local(results: list[dict], summary: dict):
    """Save scan results to local JSON files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save individual scores
    scores_file = DATA_DIR / f"scores_{timestamp}.json"
    with open(scores_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info(f"Scores saved: {scores_file}")
    
    # Save summary
    summary_file = DATA_DIR / f"summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    log.info(f"Summary saved: {summary_file}")
    
    # Save latest (overwrite) for easy access
    latest_file = DATA_DIR / "latest_scores.json"
    with open(latest_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    latest_summary = DATA_DIR / "latest_summary.json"
    with open(latest_summary, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


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
    
    for result in results:
        try:
            # Upsert server
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
            
        except Exception as e:
            log.error(f"Supabase write error for {result['server_name']}: {e}")
    
    # Save summary
    try:
        client.table("scan_summaries").upsert(
            {**summary, "source": "smithery", "scan_date": datetime.now().strftime("%Y-%m-%d")},
            on_conflict="source,scan_date"
        ).execute()
    except Exception as e:
        log.error(f"Supabase summary error: {e}")
    
    log.info("Saved to Supabase")


def run_scan(limit: int = None, dry_run: bool = False, use_supabase: bool = False, verbose: bool = False):
    """Main scan orchestrator."""
    client = httpx.Client(timeout=30)
    
    # Step 1: Get server list
    log.info("Step 1: Fetching server list from Smithery...")
    servers = fetch_server_list(client, max_servers=limit)
    log.info(f"Got {len(servers)} servers")
    
    # Step 2: Fetch details and score
    log.info("Step 2: Fetching tool definitions and scoring...")
    results = []
    scored = 0
    skipped = 0
    errors = 0
    
    for i, server in enumerate(servers):
        qname = server.get("qualifiedName", "")
        if not qname:
            skipped += 1
            continue
        
        # Fetch full detail
        detail = fetch_server_detail(client, qname)
        if not detail:
            skipped += 1
            continue
        
        tools = detail.get("tools", [])
        if not tools:
            skipped += 1
            continue
        
        # Score
        try:
            score_result = score_server(qname, tools)
            score_dict = to_json(score_result)
            
            # Add metadata from list response
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
            
            results.append(score_dict)
            scored += 1
            
            if verbose:
                print(format_report(score_result))
                print()
            
        except Exception as e:
            log.error(f"Scoring error for {qname}: {e}")
            errors += 1
        
        # Progress
        if (i + 1) % 25 == 0:
            log.info(f"Progress: {i+1}/{len(servers)} ({scored} scored, {skipped} skipped, {errors} errors)")
        
        time.sleep(0.5)  # Rate limit
    
    # Build summary
    avg_score = round(sum(r["average_score"] for r in results) / len(results), 1) if results else 0
    
    summary = {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "total_in_registry": len(servers),
        "scored": scored,
        "skipped": skipped,
        "errors": errors,
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
    print(f"ToolRank Ecosystem Scan Complete")
    print(f"=" * 60)
    print(f"Servers in registry: {len(servers)}")
    print(f"Scored: {scored} | Skipped: {skipped} | Errors: {errors}")
    print(f"Average ToolRank Score: {avg_score}/100")
    print(f"\nDistribution:")
    for level, count in summary["distribution"].items():
        bar = "█" * (count // max(1, scored // 40))
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
    parser = argparse.ArgumentParser(description="ToolRank Auto Scanner v0.2")
    parser.add_argument("--limit", type=int, help="Max servers to scan (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save results")
    parser.add_argument("--supabase", action="store_true", help="Also save to Supabase")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each server's report")
    args = parser.parse_args()
    
    run_scan(
        limit=args.limit,
        dry_run=args.dry_run,
        use_supabase=args.supabase,
        verbose=args.verbose,
    )
