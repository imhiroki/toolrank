#!/usr/bin/env python3
"""
ToolRank Layer 2: Selection Tournament Engine
=============================================
Runs LLM-based selection tests to measure real agent preference.

Counter to: "Runtime-first evaluation" attack vector.
Strategy: Ship Layer 2 BEFORE competitors can claim "static-only."

How it works:
1. Pull N servers from Supabase (same category or random pool)
2. For each round: present 3-5 tool descriptions to Claude Sonnet
3. Give a realistic task prompt → LLM picks the best tool
4. Track wins/losses per server across 100 rounds
5. Store selection_rate in DB, update trust_tiers

Usage:
  python selection_tournament.py --category filesystem --rounds 100
  python selection_tournament.py --server-ids "id1,id2,id3" --rounds 50
  python selection_tournament.py --all --rounds 100 --dry-run
"""

import os
import sys
import json
import random
import argparse
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    os.system(f"{sys.executable} -m pip install httpx --break-system-packages -q")
    import httpx

# ── Config ──────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

MODEL = "claude-sonnet-4-20250514"
MATCHUP_SIZE = 4          # tools per round
DEFAULT_ROUNDS = 100
RATE_LIMIT_DELAY = 0.5    # seconds between API calls

# ── Task Templates ──────────────────────────────────────────
# Realistic agent tasks that test whether LLMs pick the right tool
TASK_TEMPLATES = [
    {
        "category": "filesystem",
        "tasks": [
            "Read the contents of config.yaml and extract the database connection string",
            "Find all Python files modified in the last 24 hours",
            "Create a backup of the src/ directory as a zip archive",
            "Watch the logs/ directory for new files and report changes",
            "Search for TODO comments across all TypeScript files in the project",
        ]
    },
    {
        "category": "database",
        "tasks": [
            "Query the users table for accounts created this week and return as JSON",
            "Insert a new record into the orders table with the given parameters",
            "Run a migration to add an 'email_verified' column to the users table",
            "Export the last 1000 transactions as a CSV file",
            "Check database connection health and report table sizes",
        ]
    },
    {
        "category": "api",
        "tasks": [
            "Fetch the current weather for Tokyo and format it as a readable summary",
            "Send a POST request to the webhook endpoint with the deployment status",
            "Paginate through the GitHub API to get all issues for this repository",
            "Upload a file to S3 and return the public URL",
            "Check the rate limit status for the Twitter API",
        ]
    },
    {
        "category": "development",
        "tasks": [
            "Run the test suite and report any failures with stack traces",
            "Lint the codebase and auto-fix formatting issues",
            "Generate TypeScript types from the OpenAPI spec",
            "Set up a local development environment with the correct Node version",
            "Deploy the application to the staging environment",
        ]
    },
    {
        "category": "communication",
        "tasks": [
            "Send a Slack message to the #engineering channel about the deployment",
            "Draft and send an email summarizing the weekly sprint progress",
            "Create a GitHub issue for the bug reported in the support ticket",
            "Post a notification to the team's Discord channel",
            "Schedule a calendar event for the design review meeting",
        ]
    },
    {
        "category": "data",
        "tasks": [
            "Parse this CSV file and generate summary statistics",
            "Convert the JSON data into a formatted markdown table",
            "Scrape the pricing page and extract the plan details",
            "Clean and deduplicate the customer email list",
            "Generate a chart showing monthly revenue trends",
        ]
    },
    {
        "category": "general",
        "tasks": [
            "Help me understand the error in this Python traceback",
            "Summarize the key points from this PDF document",
            "Translate this technical documentation from English to Japanese",
            "Generate a UUID and format the current timestamp in ISO 8601",
            "Calculate the hash of this file and verify its integrity",
        ]
    },
]

# ── Selection Prompt ────────────────────────────────────────
SELECTION_SYSTEM_PROMPT = """You are an AI agent selecting the best MCP tool for a given task.
You will be shown several MCP server tool definitions and a task to accomplish.
Pick the single best tool for the task.

Rules:
- Consider tool name clarity, description quality, parameter precision, and fitness for the task
- A well-documented tool with clear parameters is preferred over a vague one
- If multiple tools could work, pick the one whose description most precisely matches the task
- Respond with ONLY a JSON object: {"selected": "server_id", "reason": "one sentence"}
- Do NOT explain further. Just the JSON."""

SELECTION_USER_PROMPT = """## Task
{task}

## Available Tools
{tools_json}

Pick the best tool. Respond with only: {{"selected": "<server_id>", "reason": "<one sentence>"}}"""


# ── Supabase Client ─────────────────────────────────────────
class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.client = httpx.Client(timeout=30)

    def get_servers(self, category: Optional[str] = None, limit: int = 200):
        """Fetch servers with their tools for tournament pool."""
        # Use latest_scores view for ranked servers
        url = f"{self.url}/rest/v1/latest_scores?select=*&is_test=eq.false&order=total_score.desc&limit={limit}"
        if category:
            url += f"&category=eq.{category}"
        r = self.client.get(url, headers=self.headers)
        r.raise_for_status()
        servers = r.json()

        # Enrich with tools from tools table
        for s in servers:
            sid = s.get("server_id") or s.get("id")
            if sid:
                tools_url = f"{self.url}/rest/v1/tools?select=tool_name,description,input_schema&server_id=eq.{sid}"
                tr = self.client.get(tools_url, headers=self.headers)
                if tr.status_code == 200:
                    s["tools"] = [{"name": t["tool_name"], "description": t.get("description",""), "inputSchema": t.get("input_schema",{})} for t in tr.json()]
                else:
                    s["tools"] = []
                s["id"] = sid
                s["name"] = s.get("display_name") or s.get("server_name", "")
                s["score"] = s.get("total_score", 0)
        return [s for s in servers if s.get("tools")]

    def get_servers_by_ids(self, ids: list[str]):
        """Fetch specific servers by UUID."""
        id_filter = ",".join(f'"{i}"' for i in ids)
        url = f"{self.url}/rest/v1/servers?select=*&id=in.({id_filter})"
        r = self.client.get(url, headers=self.headers)
        r.raise_for_status()
        servers = r.json()
        for s in servers:
            sid = s["id"]
            tools_url = f"{self.url}/rest/v1/tools?select=tool_name,description,input_schema&server_id=eq.{sid}"
            tr = self.client.get(tools_url, headers=self.headers)
            s["tools"] = [{"name": t["tool_name"], "description": t.get("description",""), "inputSchema": t.get("input_schema",{})} for t in (tr.json() if tr.status_code == 200 else [])]
            s["name"] = s.get("display_name") or s.get("server_name", "")
            s["score"] = 0
        return [s for s in servers if s.get("tools")]

    def save_selection_result(self, result: dict):
        """Save tournament result."""
        url = f"{self.url}/rest/v1/selection_results"
        r = self.client.post(url, headers=self.headers, json=result)
        r.raise_for_status()
        return r.json()

    def upsert_trust_tier(self, server_id: str, server_name: str, selection_rate: float):
        """Update trust tier with selection results."""
        tier_status = "earned" if selection_rate >= 70.0 else "none"
        now = datetime.now(timezone.utc).isoformat()

        data = {
            "server_id": server_id,
            "server_name": server_name,
            "selection_verified": tier_status,
            "selection_verified_at": now if tier_status == "earned" else None,
            "selection_verified_rate": selection_rate,
            "selection_expires_at": None,  # Set expiry in production
            "updated_at": now,
        }

        url = f"{self.url}/rest/v1/trust_tiers"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = self.client.post(url, headers=headers, json=data)
        r.raise_for_status()
        return r.json()

    def log_audit(self, server_id: str, action: str, tier_name: str,
                  old_value: str, new_value: str, reason: str, metadata: dict = None):
        """Write audit log entry."""
        url = f"{self.url}/rest/v1/trust_audit_log"
        data = {
            "server_id": server_id,
            "action": action,
            "tier_name": tier_name,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "metadata": metadata or {},
        }
        r = self.client.post(url, headers=self.headers, json=data)
        r.raise_for_status()


# ── Claude API Client ───────────────────────────────────────
class ClaudeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=60)

    def select_tool(self, task: str, tools: list[dict]) -> dict:
        """Ask Claude to select the best tool for a task."""
        tools_json = json.dumps(tools, indent=2, ensure_ascii=False)
        user_msg = SELECTION_USER_PROMPT.format(task=task, tools_json=tools_json)

        r = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 256,
                "temperature": 0.3,  # Slight variation for robustness
                "system": SELECTION_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
        )
        r.raise_for_status()
        data = r.json()

        # Parse response
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        # Extract JSON from response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            result = json.loads(text)
            return result
        except json.JSONDecodeError:
            return {"selected": None, "reason": "Failed to parse response", "raw": text}


# ── Tournament Runner ───────────────────────────────────────
class Tournament:
    def __init__(self, servers: list[dict], rounds: int, claude: ClaudeClient,
                 db: Optional[SupabaseClient] = None, dry_run: bool = False):
        self.servers = servers
        self.rounds = rounds
        self.claude = claude
        self.db = db
        self.dry_run = dry_run

        # Win tracking
        self.wins = {s["id"]: 0 for s in servers}
        self.appearances = {s["id"]: 0 for s in servers}
        self.results = []

    def _build_tool_desc(self, server: dict) -> dict:
        """Build a tool description for the LLM prompt."""
        return {
            "server_id": server["id"],
            "name": server.get("name", "Unknown"),
            "description": server.get("description", ""),
            "tools": server.get("tools", [])[:5],  # First 5 tools
            "tool_count": len(server.get("tools", [])),
            "category": server.get("category", "general"),
        }

    def _pick_task(self, servers_in_round: list[dict]) -> str:
        """Pick a relevant task for the servers in this round."""
        # Try to match category
        categories = set(s.get("category", "general") for s in servers_in_round)

        for tmpl in TASK_TEMPLATES:
            if tmpl["category"] in categories:
                return random.choice(tmpl["tasks"])

        # Fallback to general
        general = next((t for t in TASK_TEMPLATES if t["category"] == "general"), TASK_TEMPLATES[0])
        return random.choice(general["tasks"])

    def run(self) -> dict:
        """Run the full tournament."""
        print(f"\n{'='*60}")
        print(f"  ToolRank Layer 2: Selection Tournament")
        print(f"  Servers: {len(self.servers)} | Rounds: {self.rounds}")
        print(f"  Model: {MODEL} | Matchup size: {MATCHUP_SIZE}")
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"{'='*60}\n")

        for i in range(self.rounds):
            # Select random matchup
            matchup_size = min(MATCHUP_SIZE, len(self.servers))
            contestants = random.sample(self.servers, matchup_size)

            # Track appearances
            for c in contestants:
                self.appearances[c["id"]] += 1

            # Build tool descriptions
            tools = [self._build_tool_desc(c) for c in contestants]
            task = self._pick_task(contestants)

            if self.dry_run:
                # Simulate random winner
                winner_id = random.choice([c["id"] for c in contestants])
                reason = "[DRY RUN] Random selection"
            else:
                # Call Claude API
                try:
                    result = self.claude.select_tool(task, tools)
                    winner_id = result.get("selected")
                    reason = result.get("reason", "")
                    time.sleep(RATE_LIMIT_DELAY)
                except Exception as e:
                    print(f"  [!] Round {i+1}: API error: {e}")
                    continue

            # Record win
            if winner_id and winner_id in self.wins:
                self.wins[winner_id] += 1
                round_result = {
                    "round": i + 1,
                    "task": task,
                    "contestants": [c["id"] for c in contestants],
                    "winner": winner_id,
                    "reason": reason,
                }
                self.results.append(round_result)

                winner_name = next((c.get("name", "?") for c in contestants if c["id"] == winner_id), "?")
                print(f"  Round {i+1:3d}/{self.rounds}: {winner_name:40s} ← \"{task[:50]}...\"")
            else:
                print(f"  Round {i+1:3d}/{self.rounds}: [no valid selection]")

        # Calculate final rates
        return self._finalize()

    def _finalize(self) -> dict:
        """Calculate final selection rates and save results."""
        print(f"\n{'='*60}")
        print(f"  RESULTS")
        print(f"{'='*60}")

        final_results = []
        for server in self.servers:
            sid = server["id"]
            appearances = self.appearances[sid]
            wins = self.wins[sid]
            rate = (wins / appearances * 100) if appearances > 0 else 0.0

            entry = {
                "server_id": sid,
                "server_name": server.get("name", "Unknown"),
                "model_used": MODEL,
                "total_rounds": appearances,
                "wins": wins,
                "task_categories": list(set(
                    r["task"][:30] for r in self.results if r["winner"] == sid
                ))[:10],
                "competitor_ids": list(set(
                    cid for r in self.results for cid in r["contestants"] if sid in r["contestants"]
                ))[:20],
                "run_metadata": {
                    "total_tournament_rounds": self.rounds,
                    "matchup_size": MATCHUP_SIZE,
                    "model": MODEL,
                    "dry_run": self.dry_run,
                    "run_at": datetime.now(timezone.utc).isoformat(),
                },
            }

            tier_status = "EARNED ✓" if rate >= 70 else "not earned"
            print(f"  {server.get('name', sid):40s}  "
                  f"Win Rate: {rate:5.1f}%  "
                  f"({wins}/{appearances})  "
                  f"Selection Verified: {tier_status}")

            final_results.append(entry)

            # Save to DB
            if self.db and not self.dry_run:
                try:
                    self.db.save_selection_result(entry)
                    self.db.upsert_trust_tier(sid, server.get("name", ""), rate)
                    self.db.log_audit(
                        server_id=sid,
                        action="selection_run",
                        tier_name="selection_verified",
                        old_value="",
                        new_value=f"{rate:.1f}%",
                        reason=f"Tournament: {wins}/{appearances} wins in {self.rounds} rounds",
                        metadata={"model": MODEL, "rounds": self.rounds},
                    )
                except Exception as e:
                    print(f"  [!] DB save error for {sid}: {e}")

        print(f"\n{'='*60}")
        print(f"  Tournament complete. {len(final_results)} servers scored.")
        if self.dry_run:
            print(f"  DRY RUN — no data saved to DB.")
        print(f"{'='*60}\n")

        return {
            "total_rounds": self.rounds,
            "servers_tested": len(final_results),
            "results": final_results,
        }


# ── CLI ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ToolRank Layer 2 Selection Tournament")
    parser.add_argument("--category", type=str, help="Filter servers by category")
    parser.add_argument("--server-ids", type=str, help="Comma-separated server IDs")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="Number of rounds")
    parser.add_argument("--all", action="store_true", help="Run against all canonical servers")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without API calls")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    # Validate env
    if not args.dry_run and not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARNING: Supabase not configured. Results won't be saved to DB.")
        db = None
    else:
        db = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)

    claude = ClaudeClient(ANTHROPIC_API_KEY)

    # Fetch servers
    if args.server_ids:
        ids = [i.strip() for i in args.server_ids.split(",")]
        servers = db.get_servers_by_ids(ids) if db else []
    elif args.category:
        servers = db.get_servers(category=args.category) if db else []
    elif args.all:
        servers = db.get_servers(limit=500) if db else []
    else:
        print("Specify --category, --server-ids, or --all")
        sys.exit(1)

    if len(servers) < 2:
        print(f"Need at least 2 servers for tournament. Found: {len(servers)}")
        sys.exit(1)

    # Run tournament
    tournament = Tournament(
        servers=servers,
        rounds=args.rounds,
        claude=claude,
        db=db,
        dry_run=args.dry_run,
    )
    results = tournament.run()

    # Optionally save to file
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
