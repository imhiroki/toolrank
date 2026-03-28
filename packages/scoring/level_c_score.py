"""
ToolRank Level C Scoring Engine
Uses Claude API for semantic quality evaluation of MCP tool definitions.
Supplements Level A rule-based scoring with deep analysis.

Cost: ~$0.01 per tool (Claude Sonnet)
Use: Pro tier and above

Usage:
  python level_c_score.py '{"name": "...", "description": "..."}'
  python level_c_score.py --file tool.json
  python level_c_score.py --server brave  # Fetch from Smithery and score
"""

import json
import os
import sys
import argparse
import logging

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("level_c")

CLAUDE_API = "https://api.anthropic.com/v1/messages"
SMITHERY_BASE = "https://registry.smithery.ai"

SCORING_PROMPT = """You are ToolRank's Level C scoring engine. Analyze this MCP tool definition for agent-readiness quality.

Score each dimension 0-100 (not weighted yet):

1. FINDABILITY: Is the tool name searchable? Would BM25/regex find it? Is it specific enough?
2. CLARITY: Does the description clearly state purpose, usage context ("use this when..."), and return value? Would an agent know when to pick this over alternatives?
3. PRECISION: Are parameter types, descriptions, required fields, enums, and defaults properly defined? Would an agent construct a valid call on the first try?
4. EFFICIENCY: Is the definition token-efficient? Not too verbose, not too terse?

Also identify the top 3 improvements ranked by impact.

Respond in this exact JSON format (no markdown fences):
{
  "findability": <0-100>,
  "clarity": <0-100>,
  "precision": <0-100>,
  "efficiency": <0-100>,
  "analysis": "<2-3 sentence overall assessment>",
  "improvements": [
    {"dimension": "<dim>", "issue": "<what's wrong>", "fix": "<specific fix>", "impact": <1-10>}
  ]
}

Tool definition:
"""


def score_with_claude(tool_json: str) -> dict | None:
    """Score a tool definition using Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY")
        return None

    try:
        client = httpx.Client(timeout=30)
        resp = client.post(
            CLAUDE_API,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": SCORING_PROMPT + tool_json}],
            },
        )
        resp.raise_for_status()
        result = resp.json()
        text = result["content"][0]["text"]
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return None


def fetch_from_smithery(server_name: str) -> list[dict] | None:
    """Fetch tool definitions from Smithery."""
    try:
        client = httpx.Client(timeout=15)
        resp = client.get(f"{SMITHERY_BASE}/servers/{server_name}")
        if resp.status_code == 404:
            log.error(f"Server not found: {server_name}")
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("tools", [])
    except Exception as e:
        log.error(f"Smithery fetch error: {e}")
        return None


def combine_scores(level_a: dict, level_c: dict) -> dict:
    """Combine Level A (rule) and Level C (LLM) scores. 60/40 weighted average."""
    combined = {}
    for dim in ["findability", "clarity", "precision", "efficiency"]:
        max_pts = {"findability": 25, "clarity": 35, "precision": 25, "efficiency": 15}[dim]
        a_normalized = (level_a.get(dim, 0) / max_pts) * 100 if max_pts else 0
        c_score = level_c.get(dim, 0)
        combined[dim] = round(a_normalized * 0.6 + c_score * 0.4, 1)
    combined["total"] = round(sum(combined[d] for d in ["findability", "clarity", "precision", "efficiency"]) / 4, 1)
    combined["analysis"] = level_c.get("analysis", "")
    combined["improvements"] = level_c.get("improvements", [])
    return combined


def main():
    parser = argparse.ArgumentParser(description="ToolRank Level C Scoring (Claude API)")
    parser.add_argument("json", nargs="?", help="Tool definition JSON string")
    parser.add_argument("--file", help="Path to JSON file")
    parser.add_argument("--server", help="Smithery server name to fetch and score")
    args = parser.parse_args()

    tools = []

    if args.server:
        result = fetch_from_smithery(args.server)
        if not result:
            return
        tools = result
    elif args.file:
        with open(args.file) as f:
            data = json.load(f)
        tools = data.get("tools", [data]) if not isinstance(data, list) else data
    elif args.json:
        data = json.loads(args.json)
        tools = data.get("tools", [data]) if not isinstance(data, list) else data
    else:
        parser.print_help()
        return

    for tool in tools:
        tool_str = json.dumps(tool, indent=2)
        print(f"\n{'=' * 50}")
        print(f"Tool: {tool.get('name', 'unknown')}")
        print(f"{'=' * 50}")

        result = score_with_claude(tool_str)
        if result:
            print(f"\nLevel C Scores:")
            for dim in ["findability", "clarity", "precision", "efficiency"]:
                print(f"  {dim:15s}: {result.get(dim, 0)}/100")
            print(f"\nAnalysis: {result.get('analysis', '')}")
            print(f"\nImprovements:")
            for imp in result.get("improvements", []):
                print(f"  [{imp['dimension']}] {imp['issue']} → {imp['fix']} (impact: {imp['impact']}/10)")
        else:
            print("Scoring failed")


if __name__ == "__main__":
    main()
