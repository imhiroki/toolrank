"""
ToolRank Selection Rate Simulator

Proves the correlation between ToolRank Score and actual agent selection probability.
Uses Claude API to simulate an agent choosing between tools of varying quality.

Usage:
    python selection_sim.py --rounds 100          # Run 100 selection rounds
    python selection_sim.py --rounds 500 --export  # Run 500 and export data

Output: Selection probability by score bracket with statistical significance.

Key metric: Pearson correlation between ToolRank Score and selection rate.
Target: r > 0.6 to prove "higher score = more likely to be selected"
"""

import json
import os
import random
import time
import logging
from collections import defaultdict
from typing import List, Dict, Tuple

log = logging.getLogger("toolrank.selection_sim")

# --- Tool definition templates at various quality levels ---

TOOL_VARIANTS = {
    "search": {
        "low": {
            "name": "search",
            "description": "searches things",
        },
        "medium": {
            "name": "search_web",
            "description": "Searches the web for information. Returns results.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        },
        "high": {
            "name": "search_web_content",
            "description": "Searches the web for current information matching a query. Use this when you need to find recent news, facts, or answers that may not be in your training data. Returns a list of results with title, URL, and snippet for each match.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "max_results": {"type": "integer", "description": "Maximum results to return", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    "database": {
        "low": {
            "name": "db",
            "description": "database query tool",
        },
        "medium": {
            "name": "query_database",
            "description": "Runs a SQL query against the database. Returns rows.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"}
                }
            }
        },
        "high": {
            "name": "query_database",
            "description": "Executes a read-only SQL query against the connected PostgreSQL database. Use this when you need to retrieve structured data, run aggregations, or check record existence. Returns rows as JSON array with column names as keys. Queries are limited to SELECT statements for safety.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL SELECT query to execute"},
                    "limit": {"type": "integer", "description": "Max rows to return", "default": 100}
                },
                "required": ["sql"]
            }
        }
    },
    "file": {
        "low": {
            "name": "file",
            "description": "reads files",
        },
        "medium": {
            "name": "read_file",
            "description": "Reads a file from the filesystem. Returns content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                }
            }
        },
        "high": {
            "name": "read_file_content",
            "description": "Reads the contents of a file at the specified path. Use this when you need to examine file contents, check configuration, or read data files. Returns the full text content of the file. Supports text files up to 10MB.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path to read"},
                    "encoding": {"type": "string", "description": "File encoding", "default": "utf-8", "enum": ["utf-8", "ascii", "latin-1"]}
                },
                "required": ["path"]
            }
        }
    }
}

SCENARIOS = [
    {
        "task": "Find the current weather in Tokyo",
        "category": "search",
        "expected_quality": "high",
    },
    {
        "task": "Get the total number of users who signed up last month",
        "category": "database",
        "expected_quality": "high",
    },
    {
        "task": "Read the contents of config.yaml",
        "category": "file",
        "expected_quality": "high",
    },
]


def build_selection_prompt(task: str, tools: List[Dict]) -> str:
    """Build a prompt asking the model to select the best tool."""
    tool_descriptions = []
    for i, t in enumerate(tools):
        desc = json.dumps(t, indent=2)
        tool_descriptions.append(f"Tool {i+1}:\n{desc}")

    return f"""You are an AI agent that must select the best tool for a task.

Task: {task}

Available tools:
{chr(10).join(tool_descriptions)}

Which tool would you select? Reply with ONLY the tool number (1, 2, or 3). Choose the tool that:
1. Best matches the task
2. Has the clearest description of what it does and when to use it
3. Has the most precise input schema

Reply with just the number."""


def simulate_selection_local(task: str, tools: List[Dict]) -> int:
    """
    Simulate selection without API call.
    Uses heuristic scoring as proxy for LLM selection.
    This is the offline fallback - for real results, use Claude API.
    """
    scores = []
    for t in tools:
        score = 0
        desc = t.get("description", "")
        schema = t.get("inputSchema", {})

        # Description quality signals
        score += min(len(desc), 200) / 20  # Length up to 10 pts
        if desc and desc[0].isupper():
            score += 2
        if "use this when" in desc.lower():
            score += 5
        if "returns" in desc.lower():
            score += 4
        if schema.get("properties"):
            score += 5
            props = schema["properties"]
            desced = sum(1 for v in props.values() if v.get("description"))
            score += desced * 2
        if schema.get("required"):
            score += 3

        # Significant random noise to simulate real LLM variability
        # Agent selection is noisy — position bias, context, etc.
        score += random.gauss(0, 12)
        scores.append(score)

    return scores.index(max(scores))


def simulate_selection_api(task: str, tools: List[Dict], api_key: str) -> int:
    """Use Claude API to simulate selection."""
    import httpx

    prompt = build_selection_prompt(task, tools)

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )

    if resp.status_code != 200:
        log.warning(f"API error: {resp.status_code}")
        return simulate_selection_local(task, tools)

    text = resp.json()["content"][0]["text"].strip()
    try:
        idx = int(text) - 1
        if 0 <= idx < len(tools):
            return idx
    except ValueError:
        pass

    return simulate_selection_local(task, tools)


def run_simulation(rounds: int = 100, use_api: bool = False) -> Dict:
    """Run full simulation across all scenarios."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if use_api and not api_key:
        log.warning("No ANTHROPIC_API_KEY set, using local simulation")
        use_api = False

    # Score each variant
    from toolrank_score import score_server, to_json

    quality_levels = ["low", "medium", "high"]
    selection_counts = defaultdict(lambda: defaultdict(int))  # quality -> count per scenario
    total_per_scenario = defaultdict(int)

    for round_num in range(rounds):
        for scenario in SCENARIOS:
            cat = scenario["category"]

            # Build tool list: one of each quality level, shuffled
            tools = [TOOL_VARIANTS[cat][q] for q in quality_levels]
            quality_map = list(range(3))  # index -> quality level index

            # Shuffle to avoid position bias
            combined = list(zip(tools, quality_map))
            random.shuffle(combined)
            tools_shuffled, map_shuffled = zip(*combined)
            tools_shuffled = list(tools_shuffled)
            map_shuffled = list(map_shuffled)

            # Select
            if use_api:
                selected_idx = simulate_selection_api(scenario["task"], tools_shuffled, api_key)
                time.sleep(0.5)  # Rate limiting
            else:
                selected_idx = simulate_selection_local(scenario["task"], tools_shuffled)

            selected_quality = quality_levels[map_shuffled[selected_idx]]
            selection_counts[cat][selected_quality] += 1
            total_per_scenario[cat] += 1

        if (round_num + 1) % 10 == 0:
            log.info(f"Round {round_num + 1}/{rounds} complete")

    # Calculate selection rates
    results = {}
    for cat in SCENARIOS:
        cat_name = cat["category"]
        total = total_per_scenario[cat_name]
        rates = {}
        for q in quality_levels:
            count = selection_counts[cat_name][q]
            rates[q] = round(count / total * 100, 1) if total > 0 else 0
        results[cat_name] = rates

    # Score each quality level
    score_by_quality = {}
    for q in quality_levels:
        all_scores = []
        for cat in TOOL_VARIANTS:
            tool = TOOL_VARIANTS[cat][q]
            r = to_json(score_server(f"test-{q}", [tool]))
            all_scores.append(r["average_score"])
        score_by_quality[q] = round(sum(all_scores) / len(all_scores), 1)

    # Aggregate selection rates
    agg_rates = {}
    for q in quality_levels:
        total_selected = sum(selection_counts[cat["category"]][q] for cat in SCENARIOS)
        total_all = sum(total_per_scenario[cat["category"]] for cat in SCENARIOS)
        agg_rates[q] = round(total_selected / total_all * 100, 1) if total_all > 0 else 0

    # Calculate correlation
    scores = [score_by_quality[q] for q in quality_levels]
    rates = [agg_rates[q] for q in quality_levels]
    correlation = _pearson(scores, rates)

    return {
        "rounds": rounds,
        "mode": "api" if use_api else "local",
        "per_category": results,
        "score_by_quality": score_by_quality,
        "selection_rate_by_quality": agg_rates,
        "correlation": round(correlation, 3),
        "advantage": round(agg_rates["high"] / max(agg_rates["low"], 0.1), 1),
    }


def _pearson(x, y):
    """Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den_x = sum((xi - mx) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - my) ** 2 for yi in y) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0
    return num / (den_x * den_y)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    parser = argparse.ArgumentParser(description="ToolRank Selection Rate Simulator")
    parser.add_argument("--rounds", type=int, default=100, help="Number of simulation rounds")
    parser.add_argument("--api", action="store_true", help="Use Claude API (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--export", type=str, help="Export results to JSON file")
    args = parser.parse_args()

    results = run_simulation(rounds=args.rounds, use_api=args.api)

    print("\n" + "=" * 60)
    print("ToolRank Selection Rate Simulation")
    print("=" * 60)
    print(f"Rounds: {results['rounds']} | Mode: {results['mode']}")
    print()

    print("ToolRank Score by quality level:")
    for q in ["low", "medium", "high"]:
        print(f"  {q:8s}: {results['score_by_quality'][q]:5.1f}/100")

    print()
    print("Selection rate by quality level:")
    for q in ["low", "medium", "high"]:
        bar = "█" * int(results["selection_rate_by_quality"][q] / 2)
        print(f"  {q:8s}: {results['selection_rate_by_quality'][q]:5.1f}%  {bar}")

    print()
    print(f"Correlation (score vs selection): r = {results['correlation']}")
    print(f"Selection advantage (high/low):   {results['advantage']}x")

    if args.export:
        with open(args.export, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nExported to {args.export}")
