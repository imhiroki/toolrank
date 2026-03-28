"""
ToolRank Auto Scanner v0.1
Scans MCP registries daily, scores all tools (Level A), stores in DB.

Data Sources:
1. Smithery API (registry.smithery.ai/servers)
2. MCP Registry (registry.modelcontextprotocol.io) — metadata only
3. npm search (mcp-server-*) — package.json metadata

Usage:
  python scanner.py                    # Scan all sources
  python scanner.py --source smithery  # Scan Smithery only
  python scanner.py --dry-run          # Preview without DB write
"""

import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx  # pip install httpx

# Defer imports for optional DB
try:
    from supabase import create_client  # pip install supabase
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# Import scoring engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scoring"))
from toolrank_score import score_server, to_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scanner")


# --- Registry Clients ---

class SmitheryClient:
    """Fetch MCP servers from Smithery registry API."""
    
    BASE_URL = "https://registry.smithery.ai"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = httpx.Client(timeout=30)
    
    def list_servers(self, page_size: int = 50, max_pages: int = 20) -> list[dict]:
        """Fetch all servers from Smithery registry."""
        servers = []
        page = 1
        
        while page <= max_pages:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            try:
                resp = self.client.get(
                    f"{self.BASE_URL}/servers",
                    params={"pageSize": page_size, "page": page},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                log.error(f"Smithery API error (page {page}): {e}")
                break
            
            # Smithery returns { servers: [...], total: N } or similar
            page_servers = data.get("servers", data.get("items", []))
            if not page_servers:
                break
            
            servers.extend(page_servers)
            log.info(f"Smithery page {page}: {len(page_servers)} servers (total: {len(servers)})")
            
            # Check if we've fetched all
            total = data.get("total", data.get("totalCount", float("inf")))
            if len(servers) >= total:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        return servers
    
    def get_server_tools(self, server_id: str) -> list[dict]:
        """Fetch tool definitions for a specific server.
        
        Note: This depends on Smithery's API structure.
        Some servers expose tools directly in the list response.
        Others require a separate request.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            resp = self.client.get(
                f"{self.BASE_URL}/servers/{server_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("tools", [])
        except Exception as e:
            log.error(f"Smithery tool fetch error ({server_id}): {e}")
            return []


class MCPRegistryClient:
    """Fetch MCP servers from official MCP Registry."""
    
    BASE_URL = "https://registry.modelcontextprotocol.io"
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
    
    def list_servers(self) -> list[dict]:
        """Fetch server listing from official registry.
        
        Note: The official registry is a metaregistry.
        It provides metadata but may not include tool definitions.
        """
        try:
            resp = self.client.get(f"{self.BASE_URL}/servers")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error(f"MCP Registry error: {e}")
            return []


# --- DB Client ---

class ScoreDB:
    """Store scores in Supabase (or local JSON as fallback)."""
    
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.use_supabase = bool(supabase_url and supabase_key and HAS_SUPABASE)
        
        if self.use_supabase:
            self.client = create_client(supabase_url, supabase_key)
            log.info("Connected to Supabase")
        else:
            self.local_path = Path(__file__).parent / "data"
            self.local_path.mkdir(exist_ok=True)
            log.info(f"Using local JSON storage: {self.local_path}")
    
    def save_scan_result(self, source: str, server_data: dict, score_result: dict):
        """Save a scan result."""
        record = {
            "source": source,
            "server_name": score_result["server_name"],
            "server_data": server_data,
            "score_result": score_result,
            "average_score": score_result["average_score"],
            "total_issues": score_result["total_issues"],
            "critical_issues": score_result["critical_issues"],
            "tool_count": len(score_result["tools"]),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if self.use_supabase:
            try:
                self.client.table("scans").upsert(
                    record,
                    on_conflict="source,server_name"
                ).execute()
            except Exception as e:
                log.error(f"Supabase write error: {e}")
        else:
            # Local JSON fallback
            filename = f"{source}_{score_result['server_name']}.json"
            filename = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)
            with open(self.local_path / filename, "w") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
    
    def save_summary(self, source: str, summary: dict):
        """Save daily scan summary."""
        if self.use_supabase:
            try:
                self.client.table("scan_summaries").insert(summary).execute()
            except Exception as e:
                log.error(f"Supabase summary write error: {e}")
        else:
            filename = f"summary_{source}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(self.local_path / filename, "w") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)


# --- Scanner Orchestrator ---

def scan_smithery(db: ScoreDB, api_key: Optional[str] = None, dry_run: bool = False) -> dict:
    """Scan all Smithery servers and score them."""
    client = SmitheryClient(api_key=api_key)
    servers = client.list_servers()
    log.info(f"Found {len(servers)} servers on Smithery")
    
    results = []
    scored = 0
    errors = 0
    
    for server in servers:
        server_name = server.get("qualifiedName", server.get("name", "unknown"))
        tools = server.get("tools", [])
        
        # If tools not included in list response, try fetching
        if not tools:
            server_id = server.get("qualifiedName", server.get("id"))
            if server_id:
                tools = client.get_server_tools(server_id)
        
        if not tools:
            log.debug(f"No tools found for {server_name}, skipping")
            continue
        
        try:
            score_result = score_server(server_name, tools)
            score_dict = to_json(score_result)
            
            if not dry_run:
                db.save_scan_result("smithery", server, score_dict)
            
            results.append(score_dict)
            scored += 1
            
            if scored % 50 == 0:
                log.info(f"Scored {scored} servers...")
        
        except Exception as e:
            log.error(f"Scoring error for {server_name}: {e}")
            errors += 1
        
        time.sleep(0.2)  # Be gentle with rate limits
    
    summary = {
        "source": "smithery",
        "date": datetime.now(timezone.utc).isoformat(),
        "total_servers": len(servers),
        "scored_servers": scored,
        "errors": errors,
        "avg_score": round(sum(r["average_score"] for r in results) / len(results), 1) if results else 0,
        "score_distribution": {
            "dominant_85+": len([r for r in results if r["average_score"] >= 85]),
            "preferred_70_84": len([r for r in results if 70 <= r["average_score"] < 85]),
            "selectable_50_69": len([r for r in results if 50 <= r["average_score"] < 70]),
            "visible_25_49": len([r for r in results if 25 <= r["average_score"] < 50]),
            "absent_0_24": len([r for r in results if r["average_score"] < 25]),
        },
    }
    
    if not dry_run:
        db.save_summary("smithery", summary)
    
    log.info(f"Scan complete: {scored} scored, {errors} errors, avg score {summary['avg_score']}")
    return summary


# --- Entry Point ---

def main():
    parser = argparse.ArgumentParser(description="ToolRank Auto Scanner")
    parser.add_argument("--source", choices=["smithery", "mcp-registry", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB write")
    parser.add_argument("--smithery-key", type=str, help="Smithery API key")
    parser.add_argument("--supabase-url", type=str, help="Supabase project URL")
    parser.add_argument("--supabase-key", type=str, help="Supabase anon key")
    args = parser.parse_args()
    
    import os
    smithery_key = args.smithery_key or os.environ.get("SMITHERY_API_KEY")
    supabase_url = args.supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = args.supabase_key or os.environ.get("SUPABASE_KEY")
    
    db = ScoreDB(supabase_url, supabase_key)
    
    if args.source in ("smithery", "all"):
        scan_smithery(db, api_key=smithery_key, dry_run=args.dry_run)
    
    if args.source in ("mcp-registry", "all"):
        log.info("MCP Registry scanning: TBD (pending API structure verification)")


if __name__ == "__main__":
    main()
