"""
ToolRank Auto Blog Generator
Generates daily blog posts from scan data using Claude API.

Runs as GitHub Actions cron job. Generates Markdown → commits to repo → triggers Astro build.

Article types (rotated daily):
  Monday:    "New MCP servers this week" (new entries in DB)
  Tuesday:   "Category spotlight: [random category] ranked"
  Wednesday: "Tool description teardown: Why [top server] scores 95+"
  Thursday:  "5 most common ATO mistakes this month"
  Friday:    "Score movers: servers that improved this week"
  Saturday:  "Weekend read: ATO concept deep dive"
  Sunday:    (no article - full scan day)

Usage:
  python auto_blog.py                    # Generate today's article
  python auto_blog.py --type teardown    # Force specific article type
  python auto_blog.py --dry-run          # Preview without committing
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("autoblog")

CLAUDE_API = "https://api.anthropic.com/v1/messages"
BLOG_DIR = Path(__file__).parent.parent / "web" / "src" / "content" / "blog"
DATA_DIR = Path(__file__).parent.parent / "scanner" / "data"


def load_scan_data() -> dict:
    """Load latest scan summary and scores (local files or Supabase)."""
    summary_file = DATA_DIR / "latest_summary.json"
    scores_file = DATA_DIR / "latest_scores.json"

    summary = {}
    scores = []

    # Try local files first
    if summary_file.exists():
        with open(summary_file) as f:
            summary = json.load(f)
    if scores_file.exists():
        with open(scores_file) as f:
            scores = json.load(f)

    # Fallback to Supabase if no local data
    if not scores:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
            if url and key:
                db = create_client(url, key)
                # Read from latest_scores view (scores joined with servers)
                resp = db.table("latest_scores").select("*").order("total_score", desc=True).limit(200).execute()
                if resp.data:
                    scores = [{
                        "server_name": s["server_name"],
                        "display_name": s.get("display_name", ""),
                        "average_score": s.get("total_score", 0),
                        "tools": [],  # Not needed for article generation
                        "use_count": 0,
                    } for s in resp.data]
                    log.info(f"Loaded {len(scores)} scores from Supabase")
                # Get summary
                sum_resp = db.table("scan_summaries").select("*").order("scan_date", desc=True).limit(1).execute()
                if sum_resp.data:
                    summary = sum_resp.data[0].get("raw_summary", {})
        except Exception as e:
            log.warning(f"Supabase fallback failed: {e}")

    return {"summary": summary, "scores": scores}


def get_article_type(forced: str = None) -> str:
    """Determine article type based on day of week."""
    if forced:
        return forced
    
    weekday = datetime.now().weekday()
    types = {
        0: "new_servers",
        1: "category_spotlight",
        2: "teardown",
        3: "common_mistakes",
        4: "score_movers",
        5: "concept_deep_dive",
        6: None,  # Sunday = scan day, no article
    }
    return types.get(weekday)


def build_prompt(article_type: str, data: dict) -> str:
    """Build Claude API prompt for article generation."""
    summary = data.get("summary", {})
    scores = data.get("scores", [])
    
    top_5 = sorted(scores, key=lambda x: x.get("average_score", 0), reverse=True)[:5]
    bottom_5 = sorted(scores, key=lambda x: x.get("average_score", 0))[:5]
    avg = summary.get("average_score", 0)
    total = summary.get("total_in_db", len(scores))
    
    base_context = f"""You are writing a blog post for ToolRank (toolrank.dev), the first ATO (Agent Tool Optimization) platform.
    
Context:
- ToolRank scores MCP tool definitions across 4 dimensions: Findability, Clarity, Precision, Efficiency
- Current ecosystem: {total} servers scored, average score {avg}/100
- Top servers: {json.dumps([{"name": s["server_name"], "score": s["average_score"]} for s in top_5])}
- Bottom servers: {json.dumps([{"name": s["server_name"], "score": s["average_score"]} for s in bottom_5])}

Writing style:
- Technical but accessible
- Data-driven with specific numbers
- Short paragraphs (2-3 sentences max)
- Bold section headers
- Include actionable takeaways
- Link to /score for self-diagnosis, /framework for methodology, /ranking for full data
- Never use emojis
- End with a clear call to action

Output format: Markdown with YAML frontmatter (title, description, date, author). Do NOT include ```markdown fences."""

    prompts = {
        "new_servers": f"""{base_context}

Write a short article (400-600 words) about new MCP servers that appeared in the ecosystem recently. Pick 3-5 interesting ones from the data and analyze their ToolRank Scores. What do they do well? What could they improve?

Title format: "New in the MCP ecosystem: [month] [year]"
""",
        "category_spotlight": f"""{base_context}

Write a short article (400-600 words) spotlighting a specific category of MCP servers (e.g., database tools, search tools, DevOps tools). Rank them by ToolRank Score. Analyze what the top ones do differently.

Title format: "[Category] MCP servers ranked by agent-readiness"
""",
        "teardown": f"""{base_context}

Write a short article (400-600 words) analyzing why the #1 scored server ({top_5[0]["name"] if top_5 else "unknown"}, score {top_5[0]["average_score"] if top_5 else 0}) scores so high. Break down each dimension. Show what other servers can learn from it.

Title format: "Why [server name] scores {top_5[0]["average_score"] if top_5 else 0}/100 on ToolRank"
""",
        "common_mistakes": f"""{base_context}

Write a short article (400-600 words) about the most common ATO mistakes found across the ecosystem. Use data from the scan. Give specific before/after examples of descriptions.

Title format: "The 5 most common MCP tool description mistakes (and how to fix them)"
""",
        "score_movers": f"""{base_context}

Write a short article (400-600 words) about servers that have notably high or low scores and what differentiates them. Compare top performers vs bottom performers dimension by dimension.

Title format: "What separates a 95-point MCP server from a 55-point one"
""",
        "concept_deep_dive": f"""{base_context}

Write a short article (400-600 words) exploring one ATO concept in depth. Choose from: why Clarity is weighted 35%, how token efficiency affects agent selection, why tool count matters (GitHub's 40→13 reduction), or how registry presence affects findability.

Title format: "[Concept]: The most overlooked factor in agent tool selection"
""",
    }
    
    return prompts.get(article_type, prompts["common_mistakes"])


def generate_article(article_type: str, data: dict) -> str | None:
    """Call Claude API to generate article."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY env var")
        return None
    
    prompt = build_prompt(article_type, data)
    
    try:
        client = httpx.Client(timeout=60)
        resp = client.post(
            CLAUDE_API,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result["content"][0]["text"]
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return None


def save_article(content: str) -> Path:
    """Save generated article to blog content directory."""
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = f"auto-{date_str}"
    filepath = BLOG_DIR / f"{slug}.md"
    
    with open(filepath, "w") as f:
        f.write(content)
    
    log.info(f"Article saved: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="ToolRank Auto Blog Generator")
    parser.add_argument("--type", choices=[
        "new_servers", "category_spotlight", "teardown",
        "common_mistakes", "score_movers", "concept_deep_dive"
    ], help="Force article type")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    article_type = get_article_type(args.type)
    if not article_type:
        log.info("Sunday = scan day. No article generated.")
        return
    
    log.info(f"Article type: {article_type}")
    
    data = load_scan_data()
    if not data["scores"]:
        log.error("No scan data found. Run scanner first.")
        return
    
    log.info(f"Loaded {len(data['scores'])} scores")
    
    content = generate_article(article_type, data)
    if not content:
        log.error("Failed to generate article")
        return
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — Article preview:")
        print("=" * 60)
        print(content)
        return
    
    filepath = save_article(content)
    print(f"Article generated: {filepath}")


if __name__ == "__main__":
    main()
