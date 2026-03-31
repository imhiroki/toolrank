#!/usr/bin/env python3
"""
ToolRank Canonical Clean Index Builder
======================================
Counters: "Canonicalization as weapon" attack vector.
Strategy: "We clean our index BEFORE we score."

What it does:
1. Detect and flag test/tutorial/sample servers
2. Identify forks and duplicates (same tools, similar descriptions)
3. Group canonical entries (one entry per unique server)
4. Track maintenance status via GitHub API
5. Update Supabase with canonical flags

Usage:
  python canonical_index.py --scan --dry-run
  python canonical_index.py --scan --apply
  python canonical_index.py --maintenance-check
  python canonical_index.py --stats
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from difflib import SequenceMatcher

try:
    import httpx
except ImportError:
    os.system(f"{sys.executable} -m pip install httpx --break-system-packages -q")
    import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ── Test/Tutorial Detection ─────────────────────────────────
TEST_PATTERNS = [
    # Name patterns
    r"(?i)\btest[-_]?server\b",
    r"(?i)\bmy[-_]?first[-_]?mcp\b",
    r"(?i)\btutorial[-_]?",
    r"(?i)\bexample[-_]?server\b",
    r"(?i)\bdemo[-_]?server\b",
    r"(?i)\bsample[-_]?",
    r"(?i)\bhello[-_]?world\b",
    r"(?i)\btodo[-_]?app\b",
    r"(?i)\bstarter[-_]?template\b",
    r"(?i)\bboilerplate\b",
    r"(?i)\bplayground\b",
    r"(?i)\bsandbox\b",
    r"(?i)\bquickstart\b",
    r"(?i)\bgetting[-_]?started\b",
    r"(?i)\blearning[-_]?mcp\b",
    r"(?i)\bpractice\b",
    r"(?i)\bworkshop\b",
    r"(?i)\bcookbook[-_]?example\b",
    r"(?i)\btest[-_]?tool\b",
]

# Description patterns that indicate test/tutorial
TEST_DESC_PATTERNS = [
    r"(?i)this is a (test|sample|demo|tutorial|example)",
    r"(?i)for (testing|learning|demonstration|educational) purposes",
    r"(?i)follow along with",
    r"(?i)in this tutorial",
    r"(?i)example (mcp|server) (for|to) (learn|show|demonstrate)",
    r"(?i)starter (template|kit|project)",
    r"(?i)hello world",
    r"(?i)toy (server|project|example)",
    r"(?i)just a (test|demo|sample)",
]

# Tool name patterns (servers with generic tool names are likely tests)
TEST_TOOL_PATTERNS = [
    r"(?i)^(add|hello|greet|echo|ping|test|sample)$",
    r"(?i)^get[-_]?(greeting|hello|test)$",
    r"(?i)^say[-_]?hello$",
]


def is_test_server(server: dict) -> tuple[bool, str]:
    """Check if a server is a test/tutorial/sample entry."""
    name = server.get("name", "")
    desc = server.get("description", "")
    tools = server.get("tools", [])
    repo = server.get("repo_url", "")

    # Check name
    for pat in TEST_PATTERNS:
        if re.search(pat, name):
            return True, f"Name matches test pattern: {pat}"

    # Check description
    for pat in TEST_DESC_PATTERNS:
        if re.search(pat, desc):
            return True, f"Description matches test pattern: {pat}"

    # Check repo path
    if repo:
        repo_lower = repo.lower()
        test_repo_patterns = ["/test-", "/example-", "/tutorial-", "/demo-",
                              "/sample-", "/my-first-", "/hello-world",
                              "/learn-mcp", "/mcp-tutorial"]
        for trp in test_repo_patterns:
            if trp in repo_lower:
                return True, f"Repo path matches: {trp}"

    # Check tools: if all tools match test patterns
    if tools and len(tools) <= 3:
        tool_names = [t.get("name", "") for t in tools]
        all_test = all(
            any(re.search(tp, tn) for tp in TEST_TOOL_PATTERNS)
            for tn in tool_names if tn
        )
        if all_test and tool_names:
            return True, f"All tools match test patterns: {tool_names}"

    return False, ""


# ── Fork/Duplicate Detection ────────────────────────────────
def normalize_for_comparison(text: str) -> str:
    """Normalize text for similarity comparison."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def tools_signature(tools: list) -> str:
    """Create a signature from tool names for dedup."""
    names = sorted(t.get("name", "").lower() for t in tools if t.get("name"))
    return "|".join(names)


def detect_duplicates(servers: list[dict], threshold: float = 0.85) -> list[dict]:
    """
    Detect duplicate/similar servers.
    Returns groups of duplicates with canonical selection.
    """
    groups = defaultdict(list)

    # Phase 1: Exact tool signature match
    sig_map = defaultdict(list)
    for s in servers:
        sig = tools_signature(s.get("tools", []))
        if sig and sig != "":
            sig_map[sig].append(s)

    group_id = 0
    assigned = set()

    for sig, group in sig_map.items():
        if len(group) >= 2:
            group_id += 1
            gid = f"dup_tools_{group_id}"
            for s in group:
                if s["id"] not in assigned:
                    groups[gid].append(s)
                    assigned.add(s["id"])

    # Phase 2: Description similarity (for remaining unassigned)
    unassigned = [s for s in servers if s["id"] not in assigned]
    for i, s1 in enumerate(unassigned):
        for s2 in unassigned[i+1:]:
            if s2["id"] in assigned:
                continue
            desc1 = normalize_for_comparison(s1.get("description", ""))
            desc2 = normalize_for_comparison(s2.get("description", ""))
            if desc1 and desc2:
                ratio = SequenceMatcher(None, desc1, desc2).ratio()
                if ratio >= threshold:
                    group_id += 1
                    gid = f"dup_desc_{group_id}"
                    groups[gid].append(s1)
                    groups[gid].append(s2)
                    assigned.add(s1["id"])
                    assigned.add(s2["id"])

    # Phase 3: Repo fork detection (same repo org pattern)
    repo_groups = defaultdict(list)
    for s in servers:
        repo = s.get("repo_url", "")
        if repo:
            # Extract repo name (last part of URL)
            parts = repo.rstrip("/").split("/")
            if len(parts) >= 2:
                repo_name = parts[-1].lower()
                repo_groups[repo_name].append(s)

    for repo_name, group in repo_groups.items():
        if len(group) >= 2:
            group_id += 1
            gid = f"dup_fork_{group_id}"
            for s in group:
                if s["id"] not in assigned:
                    groups[gid].append(s)
                    assigned.add(s["id"])

    return groups


def select_canonical(group: list[dict]) -> dict:
    """Select the canonical entry from a duplicate group."""
    # Prefer: highest score → most stars → most tools → most recent
    return max(group, key=lambda s: (
        s.get("score", 0),
        s.get("github_stars", 0),
        len(s.get("tools", [])),
        s.get("updated_at", ""),
    ))


# ── Maintenance Status Check ────────────────────────────────
def check_maintenance(server: dict, gh_client: httpx.Client) -> dict:
    """Check GitHub repo for maintenance signals."""
    repo_url = server.get("repo_url", "")
    if not repo_url or "github.com" not in repo_url:
        return {"status": "unknown", "reason": "No GitHub repo"}

    # Extract owner/repo
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        return {"status": "unknown", "reason": "Could not parse repo URL"}

    owner, repo = match.group(1), match.group(2).rstrip("/").replace(".git", "")

    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        r = gh_client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        if r.status_code == 404:
            return {"status": "abandoned", "reason": "Repository not found (404)"}
        r.raise_for_status()

        data = r.json()
        pushed_at = data.get("pushed_at", "")
        archived = data.get("archived", False)
        stars = data.get("stargazers_count", 0)
        is_fork = data.get("fork", False)
        parent_url = data.get("parent", {}).get("html_url", "") if is_fork else ""

        # Determine status
        if archived:
            return {"status": "abandoned", "reason": "Repository archived",
                    "stars": stars, "last_push": pushed_at, "is_fork": is_fork}

        if pushed_at:
            last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - last_push
            if age > timedelta(days=365):
                status = "abandoned"
                reason = f"No commits in {age.days} days"
            elif age > timedelta(days=180):
                status = "inactive"
                reason = f"No commits in {age.days} days"
            else:
                status = "active"
                reason = f"Last commit {age.days} days ago"
        else:
            status = "unknown"
            reason = "No push data"

        return {
            "status": status,
            "reason": reason,
            "stars": stars,
            "last_push": pushed_at,
            "is_fork": is_fork,
            "fork_of": parent_url,
        }
    except Exception as e:
        return {"status": "unknown", "reason": f"API error: {e}"}


# ── Main Scan Pipeline ──────────────────────────────────────
class CanonicalIndexBuilder:
    def __init__(self, db_url: str, db_key: str, dry_run: bool = True):
        self.dry_run = dry_run
        self.client = httpx.Client(timeout=30)
        self.db_url = db_url.rstrip("/")
        self.db_headers = {
            "apikey": db_key,
            "Authorization": f"Bearer {db_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.stats = {
            "total": 0,
            "test_flagged": 0,
            "duplicates_found": 0,
            "forks_detected": 0,
            "canonical_selected": 0,
            "abandoned": 0,
            "active": 0,
        }

    def fetch_all_servers(self) -> list[dict]:
        """Fetch all servers with scores from Supabase."""
        url = f"{self.db_url}/rest/v1/latest_scores?select=*&order=total_score.desc&limit=2000"
        r = self.client.get(url, headers=self.db_headers)
        r.raise_for_status()
        data = r.json()
        # Map view fields to expected fields
        for s in data:
            s["id"] = s.get("server_id", s.get("id"))
            s["name"] = s.get("display_name") or s.get("server_name", "")
            s["description"] = s.get("description", "")
            s["repo_url"] = s.get("repository_url", "")
            s["score"] = s.get("total_score", 0)
            s["tools"] = []  # tools not in view, loaded separately if needed
        return data

    def update_server(self, server_id: str, updates: dict):
        """Update server record in Supabase."""
        if self.dry_run:
            return
        url = f"{self.db_url}/rest/v1/servers?id=eq.{server_id}"
        headers = {**self.db_headers, "Prefer": "return=representation"}
        r = self.client.patch(url, headers=headers, json=updates)
        r.raise_for_status()

    def run_scan(self):
        """Full canonical index scan."""
        print(f"\n{'='*60}")
        print(f"  ToolRank Canonical Clean Index Builder")
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE APPLY'}")
        print(f"{'='*60}\n")

        servers = self.fetch_all_servers()
        self.stats["total"] = len(servers)
        print(f"  Fetched {len(servers)} servers\n")

        # Phase 1: Test/tutorial detection
        print("  ── Phase 1: Test/Tutorial Detection ──")
        for s in servers:
            is_test, reason = is_test_server(s)
            if is_test:
                self.stats["test_flagged"] += 1
                print(f"  [TEST] {s.get('name', '?'):40s} → {reason}")
                self.update_server(s["id"], {"is_test": True, "is_canonical": False})
                s["_flagged_test"] = True

        print(f"\n  Flagged: {self.stats['test_flagged']} test/tutorial servers\n")

        # Phase 2: Duplicate detection
        print("  ── Phase 2: Duplicate Detection ──")
        clean_servers = [s for s in servers if not s.get("_flagged_test")]
        dup_groups = detect_duplicates(clean_servers)

        for gid, group in dup_groups.items():
            canonical = select_canonical(group)
            self.stats["canonical_selected"] += 1
            print(f"\n  Group [{gid}] — Canonical: {canonical.get('name', '?')}")

            for s in group:
                self.stats["duplicates_found"] += 1
                is_canonical = s["id"] == canonical["id"]
                status = "CANONICAL" if is_canonical else "DUPLICATE"
                print(f"    [{status}] {s.get('name', '?'):40s} (score: {s.get('score', 0)})")

                self.update_server(s["id"], {
                    "is_canonical": is_canonical,
                    "canonical_id": None if is_canonical else canonical["id"],
                    "duplicate_group": gid,
                })

        print(f"\n  Found: {self.stats['duplicates_found']} duplicates in {len(dup_groups)} groups\n")

        # Phase 3: Fork detection via GitHub
        if GITHUB_TOKEN:
            print("  ── Phase 3: Maintenance & Fork Check ──")
            gh_client = httpx.Client(timeout=15)
            checked = 0
            for s in clean_servers[:100]:  # Rate limit: check 100 at a time
                if s.get("_flagged_test"):
                    continue
                result = check_maintenance(s, gh_client)
                checked += 1

                if result["status"] == "abandoned":
                    self.stats["abandoned"] += 1
                    print(f"  [ABANDONED] {s.get('name', '?'):40s} → {result['reason']}")
                elif result["status"] == "active":
                    self.stats["active"] += 1

                updates = {
                    "maintenance_status": result["status"],
                    "github_stars": result.get("stars", 0),
                    "last_commit_at": result.get("last_push"),
                }
                if result.get("is_fork"):
                    updates["is_fork"] = True
                    updates["fork_of"] = result.get("fork_of", "")
                    self.stats["forks_detected"] += 1
                    print(f"  [FORK]      {s.get('name', '?'):40s} → fork of {result.get('fork_of', '?')}")

                self.update_server(s["id"], updates)

                if checked % 20 == 0:
                    print(f"  ... checked {checked} repos")

            print(f"\n  Checked: {checked} repos")
            print(f"  Active: {self.stats['active']} | Abandoned: {self.stats['abandoned']} | Forks: {self.stats['forks_detected']}")
        else:
            print("  ── Phase 3: Skipped (no GITHUB_TOKEN) ──")

        # Summary
        print(f"\n{'='*60}")
        print(f"  CANONICAL INDEX SUMMARY")
        print(f"{'='*60}")
        print(f"  Total servers scanned:  {self.stats['total']}")
        print(f"  Test/tutorial flagged:  {self.stats['test_flagged']}")
        print(f"  Duplicates found:       {self.stats['duplicates_found']}")
        print(f"  Forks detected:         {self.stats['forks_detected']}")
        print(f"  Abandoned repos:        {self.stats['abandoned']}")
        print(f"  Clean canonical count:  {self.stats['total'] - self.stats['test_flagged'] - self.stats['duplicates_found'] + self.stats['canonical_selected']}")
        if self.dry_run:
            print(f"\n  DRY RUN — no changes applied. Use --apply to write.")
        print(f"{'='*60}\n")

        return self.stats


def main():
    parser = argparse.ArgumentParser(description="ToolRank Canonical Clean Index Builder")
    parser.add_argument("--scan", action="store_true", help="Run full canonical scan")
    parser.add_argument("--maintenance-check", action="store_true", help="Check maintenance status only")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--stats", action="store_true", help="Show current index stats")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)

    dry_run = not args.apply or args.dry_run
    builder = CanonicalIndexBuilder(SUPABASE_URL, SUPABASE_KEY, dry_run=dry_run)

    if args.scan or args.maintenance_check:
        builder.run_scan()
    elif args.stats:
        servers = builder.fetch_all_servers()
        total = len(servers)
        tests = sum(1 for s in servers if s.get("is_test"))
        canonical = sum(1 for s in servers if s.get("is_canonical", True) and not s.get("is_test"))
        print(f"Total: {total} | Tests: {tests} | Canonical: {canonical}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
