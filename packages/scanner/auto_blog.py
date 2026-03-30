"""
ToolRank Auto Content Generator (Claude API)
Generates daily data-driven blog posts using Claude API + scan data.
Each article is unique, analytical, and designed to be cited/linked.

Article types (rotated daily):
  Monday:    "Ecosystem Pulse" — weekly stats, trends, new entries
  Tuesday:   "Server Spotlight" — deep dive on a notable server
  Wednesday: "Score Movers" — who improved, who declined, why
  Thursday:  "Category Ranking" — top servers in a category
  Friday:    "ATO Tips" — pattern-based improvement advice

Monthly (1st of month):
  "State of MCP" — comprehensive monthly report (highest link bait)

Usage:
  python auto_blog.py                    # Generate today's article
  python auto_blog.py --type spotlight   # Force specific type
  python auto_blog.py --dry-run          # Preview without writing
  python auto_blog.py --monthly          # Generate monthly State of MCP
"""

import json, os, sys, argparse, logging, hashlib, random
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx"); sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("autoblog")

CLAUDE_API = "https://api.anthropic.com/v1/messages"
BLOG_DIR = Path(__file__).parent.parent / "web" / "src" / "content" / "blog"

ARTICLE_TYPES = {
    0: "pulse",      # Monday
    1: "spotlight",   # Tuesday
    2: "movers",      # Wednesday
    3: "category",    # Thursday
    4: "tips",        # Friday
}

CATEGORIES = [
    "search", "database", "file-management", "code-analysis", "web-scraping",
    "finance", "weather", "communication", "data-processing", "security",
    "ai-ml", "documentation", "monitoring", "translation", "calendar",
]


def load_scan_data():
    """Load latest scores from Supabase."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return None

    client = httpx.Client(timeout=30)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    # Latest scores
    resp = client.get(
        f"{url}/rest/v1/latest_scores?order=total_score.desc&limit=500",
        headers=headers
    )
    scores = resp.json() if resp.status_code == 200 else []

    # Scan history
    resp2 = client.get(
        f"{url}/rest/v1/scan_summaries?order=scan_date.desc&limit=30",
        headers=headers
    )
    history = resp2.json() if resp2.status_code == 200 else []

    client.close()
    return {"scores": scores, "history": history}


def build_context(data, article_type):
    """Build context string for Claude based on article type."""
    scores = data["scores"]
    history = data["history"]

    total = len(scores)
    avg = sum(s.get("total_score", 0) for s in scores) / total if total else 0
    dominant = sum(1 for s in scores if s.get("total_score", 0) >= 85)
    preferred = sum(1 for s in scores if 70 <= s.get("total_score", 0) < 85)
    selectable = sum(1 for s in scores if 50 <= s.get("total_score", 0) < 70)

    base = f"""ToolRank Ecosystem Data (as of {datetime.now().strftime('%Y-%m-%d')}):
- Total scored servers: {total}
- Average score: {avg:.1f}/100
- Distribution: {dominant} Dominant (85+), {preferred} Preferred (70-84), {selectable} Selectable (50-69)
- Sources: Smithery + Official MCP Registry (4,000+ scanned, ~73% have no tool definitions)

Top 10 servers:
"""
    for s in scores[:10]:
        base += f"  {s.get('display_name', s['server_name'])} ({s['server_name']}): {round(s['total_score'])}/100 F:{round(s.get('findability',0))} C:{round(s.get('clarity',0))} P:{round(s.get('precision',0))} E:{round(s.get('efficiency',0))}\n"

    if article_type == "spotlight":
        # Pick a random top-20 server for deep dive
        target = random.choice(scores[:20])
        base += f"\nSpotlight server: {target.get('display_name', target['server_name'])} ({target['server_name']})\n"
        base += f"  Score: {round(target['total_score'])}/100\n"
        base += f"  Tools: {target.get('tool_count', '?')}\n"
        base += f"  Source: {target.get('source', 'smithery')}\n"
        base += f"  Findability: {round(target.get('findability',0))}/25, Clarity: {round(target.get('clarity',0))}/35, Precision: {round(target.get('precision',0))}/25, Efficiency: {round(target.get('efficiency',0))}/15\n"

    elif article_type == "category":
        cat = random.choice(CATEGORIES)
        base += f"\nCategory focus: {cat}\n"
        # Find servers matching category keyword
        matches = [s for s in scores if cat.replace("-", " ") in (s.get("display_name", "") + s.get("server_name", "") + s.get("description", "")).lower()][:10]
        if matches:
            base += "Matching servers:\n"
            for s in matches:
                base += f"  {s.get('display_name', s['server_name'])}: {round(s['total_score'])}/100\n"

    elif article_type == "movers":
        if len(history) >= 2:
            latest = history[0]
            prev = history[1]
            base += f"\nTrend: avg score {prev.get('avg_score','?')} → {latest.get('avg_score','?')}\n"
            base += f"Servers: {prev.get('scored_servers','?')} → {latest.get('scored_servers','?')}\n"

    elif article_type == "tips":
        # Collect most common issues from low-scoring servers
        low = [s for s in scores if s.get("total_score", 0) < 80]
        low_clarity = sum(1 for s in low if s.get("clarity", 0) < 25)
        low_precision = sum(1 for s in low if s.get("precision", 0) < 18)
        low_findability = sum(1 for s in low if s.get("findability", 0) < 20)
        base += f"\nCommon issues in sub-80 servers ({len(low)} total):\n"
        base += f"  Low clarity (<25/35): {low_clarity} servers\n"
        base += f"  Low precision (<18/25): {low_precision} servers\n"
        base += f"  Low findability (<20/25): {low_findability} servers\n"

    elif article_type == "monthly":
        base += f"\nScan history (last 30 days): {len(history)} data points\n"
        if history:
            base += f"First scan: {history[-1].get('scan_date','?')}, Latest: {history[0].get('scan_date','?')}\n"

    bottom_5 = scores[-5:] if len(scores) >= 5 else scores
    base += "\nBottom 5 servers:\n"
    for s in bottom_5:
        base += f"  {s.get('display_name', s['server_name'])}: {round(s['total_score'])}/100\n"

    return base


SYSTEM_PROMPT = """You are a technical writer for ToolRank (toolrank.dev), an open-source platform that scores MCP tool definitions for AI agent discoverability.

Write blog articles that are:
- Data-driven: use specific numbers from the provided scan data
- Analytical: don't just list facts, explain WHY patterns exist and WHAT developers should do
- Citable: include specific claims that other writers would want to reference
- Actionable: every article should have concrete takeaways
- SEO-optimized: use natural keyword placement for "MCP tools", "AI agent", "tool optimization"

Format: Astro-compatible Markdown with frontmatter.
Required frontmatter fields (EXACTLY these names, no others):
---
title: "Article Title"
description: "A one-sentence summary"
date: "YYYY-MM-DD"
---

Do NOT include tags, pubDate, author, or any other frontmatter fields. Only title, description, and date.

IMPORTANT:
- Do NOT use placeholder or generic advice. Use the REAL data provided.
- Every claim should be backed by a number from the data.
- Link to toolrank.dev/score, toolrank.dev/ranking, toolrank.dev/framework where relevant.
- Keep articles 600-1000 words. Quality over length.
- Titles should be specific and compelling, not generic.
"""

PROMPTS = {
    "pulse": """Write a weekly ecosystem pulse article. Cover:
1. Key stats this week (total servers, average score, distribution)
2. One interesting trend or anomaly in the data
3. What this means for MCP developers
Title should include specific numbers, e.g. "374 MCP Servers Scored: What the Data Tells Us This Week"
""",
    "spotlight": """Write a server spotlight article analyzing one specific server in depth. Cover:
1. What makes this server score well (or poorly) — be specific about dimensions
2. What other developers can learn from this example
3. One specific fix that would improve the score (if applicable)
Title should name the server, e.g. "How Brave Search Hits 95/100 on ToolRank"
""",
    "movers": """Write a score movers article about changes in the ecosystem. Cover:
1. Which servers improved or declined (use data if available, otherwise discuss patterns)
2. What typically causes score changes
3. The most impactful single change a developer can make
Title should create curiosity, e.g. "The One-Line Fix That Jumped This Server from 62 to 91"
""",
    "category": """Write a category ranking article comparing servers in a specific category. Cover:
1. Top servers in this category and why they score well
2. Common patterns among high-scoring servers in this category
3. Gaps and opportunities (what's missing in this category)
Title should name the category, e.g. "The 5 Best Search MCP Servers (and What They Do Right)"
""",
    "tips": """Write an ATO tips article based on common patterns in the data. Cover:
1. The most common scoring issue and exactly how to fix it
2. A before/after example (construct a realistic one from patterns)
3. Why this issue matters for AI agent selection
Title should be specific and practical, e.g. "Why 67% of MCP Tools Lose Points on Clarity (and the 30-Second Fix)"
""",
    "monthly": """Write a comprehensive "State of MCP" monthly report. This is the most important article — designed to be THE reference that others cite. Cover:
1. Ecosystem size and growth
2. Score distribution and what it means
3. Top servers and emerging trends
4. Categories with the most/least competition
5. Predictions for next month
6. Key recommendations for developers
Title: "State of MCP — {month} {year}: {compelling subtitle}"
Make it 1000-1500 words. This is the flagship content piece.
""",
}


def generate_article(article_type, data, dry_run=False):
    """Generate article using Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY env var")
        return None

    context = build_context(data, article_type)
    prompt = PROMPTS.get(article_type, PROMPTS["pulse"])

    # Add date context
    today = datetime.now()
    prompt += f"\n\nToday's date: {today.strftime('%Y-%m-%d')}. Use this as pubDate."

    log.info(f"Generating '{article_type}' article via Claude API...")

    client = httpx.Client(timeout=120)
    resp = client.post(
        CLAUDE_API,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": f"Here is the latest ToolRank ecosystem data:\n\n{context}\n\n{prompt}"}
            ],
        },
    )
    client.close()

    if resp.status_code != 200:
        log.error(f"Claude API error: {resp.status_code} {resp.text[:200]}")
        return None

    result = resp.json()
    content = result["content"][0]["text"]

    # Extract slug from frontmatter title
    lines = content.split("\n")
    title_line = next((l for l in lines if l.startswith("title:")), "")
    title = title_line.replace("title:", "").strip().strip('"').strip("'")
    slug = title.lower()
    for ch in [" ", ":", "'", '"', "(", ")", ",", ".", "?", "!", "/", "&", "%"]:
        slug = slug.replace(ch, "-")
    slug = "-".join(p for p in slug.split("-") if p)[:60]

    # Add date prefix for uniqueness
    date_prefix = today.strftime("%Y-%m-%d")
    slug = f"{date_prefix}-{slug}"

    return {"slug": slug, "content": content, "title": title, "type": article_type}


def write_article(article, dry_run=False):
    """Write article to blog directory."""
    if dry_run:
        log.info(f"[DRY RUN] Would write: {article['slug']}.md")
        log.info(f"  Title: {article['title']}")
        log.info(f"  Type: {article['type']}")
        log.info(f"  Length: {len(article['content'])} chars")
        print("\n--- Preview ---")
        print(article["content"][:500])
        print("...")
        return True

    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    filepath = BLOG_DIR / f"{article['slug']}.md"

    # Don't overwrite
    if filepath.exists():
        log.info(f"Article already exists: {filepath.name}")
        return False

    with open(filepath, "w") as f:
        f.write(article["content"])

    log.info(f"✅ Wrote: {filepath.name} ({len(article['content'])} chars)")
    return True


def main():
    parser = argparse.ArgumentParser(description="ToolRank Auto Content Generator")
    parser.add_argument("--type", choices=list(PROMPTS.keys()), help="Force article type")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--monthly", action="store_true", help="Generate monthly State of MCP")
    args = parser.parse_args()

    # Determine article type
    if args.monthly:
        article_type = "monthly"
    elif args.type:
        article_type = args.type
    else:
        dow = datetime.now().weekday()
        article_type = ARTICLE_TYPES.get(dow, "pulse")

    log.info(f"Article type: {article_type}")

    # Load data
    data = load_scan_data()
    if not data or not data["scores"]:
        log.error("No scan data available")
        sys.exit(1)

    log.info(f"Loaded {len(data['scores'])} scores, {len(data['history'])} history points")

    # Generate
    article = generate_article(article_type, data, args.dry_run)
    if not article:
        log.error("Article generation failed")
        sys.exit(1)

    # Write
    write_article(article, args.dry_run)


if __name__ == "__main__":
    main()
