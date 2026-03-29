"""
ToolRank Multi-Registry Scanner
Fetches MCP servers from multiple registries and deduplicates.

Supported registries:
1. Smithery (registry.smithery.ai) — existing
2. Official MCP Registry (registry.modelcontextprotocol.io) — NEW
3. MCP.so (mcp.so/api) — NEW (if API available)

Usage:
    python multi_registry.py --list          # List all servers from all registries
    python multi_registry.py --stats         # Show per-registry stats
    python multi_registry.py --export json   # Export unified server list
"""

import httpx
import json
import time
import logging
from typing import List, Dict, Optional, Tuple

log = logging.getLogger("toolrank.multi_registry")

# --- Registry Adapters ---

class RegistryAdapter:
    """Base class for registry adapters."""
    name: str = "unknown"
    base_url: str = ""

    def fetch_servers(self, client: httpx.Client, limit: int = 0) -> List[Dict]:
        raise NotImplementedError

    def normalize(self, raw: Dict) -> Optional[Dict]:
        """Normalize to ToolRank canonical format."""
        raise NotImplementedError


class SmitheryAdapter(RegistryAdapter):
    """Smithery Registry (existing)."""
    name = "smithery"
    base_url = "https://registry.smithery.ai"

    def fetch_servers(self, client: httpx.Client, limit: int = 0) -> List[Dict]:
        servers = []
        page_size = 100
        url = f"{self.base_url}/servers?pageSize={page_size}"

        while url:
            try:
                resp = client.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("servers", [])
                servers.extend(batch)
                log.info(f"[smithery] Fetched {len(batch)} servers (total: {len(servers)})")

                if limit and len(servers) >= limit:
                    return servers[:limit]

                next_cursor = data.get("nextCursor")
                url = f"{self.base_url}/servers?pageSize={page_size}&cursor={next_cursor}" if next_cursor else None
                time.sleep(1)
            except Exception as e:
                log.error(f"[smithery] Error: {e}")
                break

        return servers

    def normalize(self, raw: Dict) -> Optional[Dict]:
        qn = raw.get("qualifiedName", "")
        if not qn:
            return None
        return {
            "canonical_id": f"smithery:{qn}",
            "name": raw.get("displayName", qn),
            "qualified_name": qn,
            "description": raw.get("description", ""),
            "source": "smithery",
            "homepage": raw.get("homepage", ""),
            "repository": raw.get("repository", ""),
            "tools": raw.get("tools", []),
            "raw": raw,
        }


class OfficialRegistryAdapter(RegistryAdapter):
    """Official MCP Registry (registry.modelcontextprotocol.io)."""
    name = "official"
    base_url = "https://registry.modelcontextprotocol.io"

    def fetch_servers(self, client: httpx.Client, limit: int = 0) -> List[Dict]:
        servers = []
        # Try v0.1 first (stable), fall back to v0
        for version in ["v0.1", "v0"]:
            url = f"{self.base_url}/{version}/servers?limit=100"
            try:
                resp = client.get(url, timeout=30)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()

                # Handle paginated response
                batch = data.get("servers", data.get("items", []))
                if isinstance(data, list):
                    batch = data
                servers.extend(batch)
                log.info(f"[official/{version}] Fetched {len(batch)} servers")

                # Paginate
                next_cursor = data.get("metadata", {}).get("nextCursor") or data.get("nextCursor")
                while next_cursor:
                    if limit and len(servers) >= limit:
                        break
                    page_url = f"{self.base_url}/{version}/servers?limit=100&cursor={next_cursor}"
                    try:
                        resp = client.get(page_url, timeout=30)
                        resp.raise_for_status()
                        data = resp.json()
                        batch = data.get("servers", data.get("items", []))
                        if isinstance(data, list):
                            batch = data
                        servers.extend(batch)
                        log.info(f"[official/{version}] Fetched {len(batch)} more (total: {len(servers)})")
                        next_cursor = data.get("metadata", {}).get("nextCursor") or data.get("nextCursor")
                        time.sleep(1)
                    except Exception as e:
                        log.error(f"[official/{version}] Pagination error: {e}")
                        break

                if servers:
                    break  # Success, don't try other version
            except Exception as e:
                log.warning(f"[official/{version}] Error: {e}")
                continue

        return servers[:limit] if limit else servers

    def normalize(self, raw: Dict) -> Optional[Dict]:
        # Official registry uses different field names
        server_id = raw.get("id", raw.get("name", raw.get("qualified_name", "")))
        if not server_id:
            return None

        name = raw.get("name", raw.get("display_name", server_id))
        desc = raw.get("description", "")
        repo = raw.get("repository", raw.get("source_url", ""))
        homepage = raw.get("homepage", "")

        # Extract tools if available
        tools = raw.get("tools", [])
        if not tools:
            # Some entries have tools under versions
            versions = raw.get("versions", [])
            if versions and isinstance(versions, list):
                latest = versions[-1] if versions else {}
                tools = latest.get("tools", [])

        return {
            "canonical_id": f"official:{server_id}",
            "name": name,
            "qualified_name": server_id,
            "description": desc,
            "source": "official",
            "homepage": homepage,
            "repository": repo,
            "tools": tools,
            "raw": raw,
        }


# --- Deduplication ---

def deduplicate(servers: List[Dict]) -> List[Dict]:
    """
    Deduplicate servers across registries.
    Priority: official > smithery > other
    Match on: qualified_name (exact), or name similarity
    """
    SOURCE_PRIORITY = {"official": 0, "smithery": 1, "mcpso": 2}

    seen = {}  # qualified_name -> best entry
    for s in servers:
        qn = s["qualified_name"].lower().strip()
        if qn in seen:
            existing = seen[qn]
            existing_priority = SOURCE_PRIORITY.get(existing["source"], 99)
            new_priority = SOURCE_PRIORITY.get(s["source"], 99)
            # Keep higher priority (lower number) or the one with more tools
            if new_priority < existing_priority:
                s["also_in"] = existing.get("also_in", []) + [existing["source"]]
                seen[qn] = s
            else:
                existing["also_in"] = existing.get("also_in", []) + [s["source"]]
        else:
            s["also_in"] = []
            seen[qn] = s

    return list(seen.values())


# --- Main ---

def fetch_all_registries(limit_per_registry: int = 0) -> Tuple[List[Dict], Dict]:
    """Fetch from all registries, normalize, deduplicate."""
    adapters = [
        OfficialRegistryAdapter(),
        SmitheryAdapter(),
    ]

    all_servers = []
    stats = {}

    client = httpx.Client(
        headers={"User-Agent": "ToolRank/0.2 (+https://toolrank.dev)"},
        follow_redirects=True,
    )

    for adapter in adapters:
        log.info(f"Fetching from {adapter.name}...")
        try:
            raw_servers = adapter.fetch_servers(client, limit=limit_per_registry)
            normalized = []
            for raw in raw_servers:
                n = adapter.normalize(raw)
                if n:
                    normalized.append(n)

            all_servers.extend(normalized)
            stats[adapter.name] = {
                "raw": len(raw_servers),
                "normalized": len(normalized),
            }
            log.info(f"[{adapter.name}] {len(raw_servers)} raw → {len(normalized)} normalized")
        except Exception as e:
            log.error(f"[{adapter.name}] Failed: {e}")
            stats[adapter.name] = {"raw": 0, "normalized": 0, "error": str(e)}

    client.close()

    # Deduplicate
    before_dedup = len(all_servers)
    deduped = deduplicate(all_servers)
    stats["_total"] = {
        "before_dedup": before_dedup,
        "after_dedup": len(deduped),
        "duplicates_removed": before_dedup - len(deduped),
    }

    log.info(f"Total: {before_dedup} → {len(deduped)} after dedup ({before_dedup - len(deduped)} removed)")

    return deduped, stats


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    parser = argparse.ArgumentParser(description="ToolRank Multi-Registry Scanner")
    parser.add_argument("--list", action="store_true", help="List all servers")
    parser.add_argument("--stats", action="store_true", help="Show per-registry stats")
    parser.add_argument("--limit", type=int, default=0, help="Limit per registry (0=all)")
    parser.add_argument("--export", type=str, help="Export to JSON file")
    args = parser.parse_args()

    servers, stats = fetch_all_registries(limit_per_registry=args.limit)

    if args.stats or not (args.list or args.export):
        print("\n=== Multi-Registry Stats ===")
        for name, s in stats.items():
            if name.startswith("_"):
                print(f"\nTotal: {s['before_dedup']} raw → {s['after_dedup']} unique ({s['duplicates_removed']} duplicates)")
            else:
                print(f"  {name}: {s.get('raw', 0)} raw → {s.get('normalized', 0)} normalized")

    if args.list:
        print(f"\n=== {len(servers)} Servers ===")
        for s in sorted(servers, key=lambda x: x["qualified_name"]):
            also = f" (also: {', '.join(s.get('also_in', []))})" if s.get("also_in") else ""
            tools = len(s.get("tools", []))
            print(f"  [{s['source']:10s}] {s['qualified_name']:40s} tools={tools}{also}")

    if args.export:
        # Strip raw data for export
        export = [{k: v for k, v in s.items() if k != "raw"} for s in servers]
        with open(args.export, "w") as f:
            json.dump({"servers": export, "stats": stats}, f, indent=2, default=str)
        print(f"\nExported {len(export)} servers to {args.export}")
