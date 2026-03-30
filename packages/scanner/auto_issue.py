"""
ToolRank Auto-Issue: Send improvement suggestions to low-score MCP servers.

Finds Selectable-level servers (50-69), identifies their GitHub repos,
and creates issues with specific fix suggestions.

Usage:
    python auto_issue.py --limit 5 --dry-run    # Preview without creating
    python auto_issue.py --limit 5               # Create issues

Requires: GITHUB_TOKEN env var
"""

import os
import json
import logging
import httpx
from datetime import datetime

log = logging.getLogger("toolrank.auto_issue")

ISSUE_TITLE_TEMPLATE = "Improve MCP tool definitions for better AI agent discovery (ToolRank Score: {score}/100)"

ISSUE_BODY_TEMPLATE = """Hi! 👋

I built [ToolRank](https://toolrank.dev), an open-source tool that scores MCP server definitions for AI agent discoverability.

Your server **{name}** scored **{score}/100**, which puts it in the **{level}** tier (top {percentile}% of MCP servers).

### What this means

AI agents choose between competing tools based on description quality. Research shows optimized tools get selected **3.6x more often** (arXiv 2602.18914). At {score}/100, your tool's estimated selection rate is **{sel_rate}**.

### Quick fixes

{fixes}

### Score details

| Dimension | Score | Max |
|-----------|-------|-----|
| Findability | {f} | 25 |
| Clarity | {c} | 35 |
| Precision | {p} | 25 |
| Efficiency | {e} | 15 |

You can get specific fix suggestions at: **[toolrank.dev/score](https://toolrank.dev/score)**

---

<sub>This issue was created by [ToolRank](https://toolrank.dev) — an open-source MCP tool quality scorer. [View scoring logic](https://github.com/imhiroki/toolrank/blob/main/packages/scoring/toolrank_score.py). If you find this unhelpful, please let me know and I won't send further issues.</sub>
"""


def get_fix_suggestions(score_data):
    """Generate fix suggestions based on scores."""
    fixes = []
    f, c, p, e = score_data.get('findability', 0), score_data.get('clarity', 0), score_data.get('precision', 0), score_data.get('efficiency', 0)
    
    if c < 25:
        fixes.append("1. **Expand descriptions** to 80-200 characters with purpose, usage context, and return value")
    if c < 28:
        fixes.append("2. **Start descriptions with an action verb** (\"Searches for...\", \"Creates...\")")
    if c < 30:
        fixes.append("3. **Add usage context**: \"Use this when you need to...\"")
    if p < 18:
        fixes.append("4. **Define `required` fields** in inputSchema")
    if p < 20:
        fixes.append("5. **Add parameter descriptions** to all schema properties")
    if f < 20:
        fixes.append("6. **Use a specific tool name** (e.g., `search_repositories` instead of `search`)")
    
    if not fixes:
        fixes.append("1. Add more detailed descriptions with usage context and return values")
        fixes.append("2. Define enums and defaults for common parameters")
    
    return "\n".join(fixes)


def extract_github_repo(server_data):
    """Extract GitHub owner/repo from server metadata."""
    raw = server_data.get('raw_data', {})
    homepage = raw.get('homepage', '')
    repo = raw.get('repository', '')
    qname = server_data.get('server_name', '')
    
    for url in [repo, homepage]:
        if 'github.com' in str(url):
            parts = url.rstrip('/').split('github.com/')[-1].split('/')
            if len(parts) >= 2:
                return parts[0], parts[1].replace('.git', '')
    
    # Try qualified name as owner/repo
    if '/' in qname:
        parts = qname.split('/')
        return parts[0], parts[1]
    
    return None, None


def run(limit=5, dry_run=False, min_score=50, max_score=69):
    """Find low-score servers and create issues."""
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token and not dry_run:
        log.error("Set GITHUB_TOKEN env var")
        return

    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return

    client = httpx.Client(timeout=30)
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

    # Check which repos were contacted recently (within 30 days)
    recently_contacted = set()
    try:
        resp = client.get(
            f"{supabase_url}/rest/v1/contacted_repos?select=repo_name,contacted_at",
            headers=headers
        )
        if resp.status_code == 200:
            now = datetime.now()
            for r in resp.json():
                contacted_at = datetime.fromisoformat(r['contacted_at'].replace('Z', '+00:00').replace('+00:00', ''))
                days_ago = (now - contacted_at).days
                if days_ago < 30:
                    recently_contacted.add(r['repo_name'])
            log.info(f"{len(recently_contacted)} repos contacted in last 30 days (cooldown)")
    except Exception as e:
        log.warning(f"Could not check contacted repos: {e}")

    # Fetch low-score servers
    resp = client.get(
        f"{supabase_url}/rest/v1/latest_scores?total_score=gte.{min_score}&total_score=lte.{max_score}&order=total_score.asc&limit={limit * 3}",
        headers=headers
    )
    
    if resp.status_code != 200:
        log.error(f"Supabase error: {resp.status_code}")
        return

    servers = resp.json()
    log.info(f"Found {len(servers)} servers in score range {min_score}-{max_score}")

    created = 0
    for srv in servers:
        if created >= limit:
            break

        owner, repo = extract_github_repo(srv)
        if not owner or not repo:
            log.info(f"  Skip {srv['server_name']}: no GitHub repo found")
            continue

        repo_full = f"{owner}/{repo}"
        if repo_full in recently_contacted:
            log.info(f"  Skip {repo_full}: contacted within last 30 days")
            continue

        score = round(srv['total_score'])
        level = 'Selectable' if score >= 50 else 'Visible'
        pct = 92 if score < 70 else 75
        sel_rate = '~2-13%' if score >= 50 else '<2%'

        fixes = get_fix_suggestions(srv)
        
        title = ISSUE_TITLE_TEMPLATE.format(score=score)
        body = ISSUE_BODY_TEMPLATE.format(
            name=srv.get('display_name', srv['server_name']),
            score=score, level=level, percentile=pct, sel_rate=sel_rate,
            fixes=fixes,
            f=round(srv.get('findability', 0)),
            c=round(srv.get('clarity', 0)),
            p=round(srv.get('precision', 0)),
            e=round(srv.get('efficiency', 0)),
        )

        if dry_run:
            log.info(f"  [DRY RUN] Would create issue on {owner}/{repo}: {title}")
            created += 1
            continue

        try:
            resp = client.post(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "ToolRank/0.2 (+https://toolrank.dev)",
                },
                json={"title": title, "body": body, "labels": ["toolrank", "mcp", "quality"]},
            )
            if resp.status_code == 201:
                log.info(f"  ✅ Created issue on {owner}/{repo} (score {score})")
                created += 1
                # Record contact in Supabase (upsert: update contacted_at if exists)
                try:
                    client.post(
                        f"{supabase_url}/rest/v1/contacted_repos",
                        headers={**headers, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"},
                        json={
                            "repo_name": repo_full,
                            "server_name": srv['server_name'],
                            "score_at_contact": score,
                            "contacted_at": datetime.now().isoformat(),
                            "issue_url": resp.json().get('html_url', ''),
                        }
                    )
                except Exception:
                    pass  # Non-critical
            elif resp.status_code == 404:
                log.info(f"  Skip {owner}/{repo}: repo not found or no permission")
            elif resp.status_code == 410:
                log.info(f"  Skip {owner}/{repo}: issues disabled")
            else:
                log.warning(f"  ⚠️ {owner}/{repo}: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            log.warning(f"  Error {owner}/{repo}: {e}")

    log.info(f"Created {created} issues (limit: {limit})")
    client.close()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-score", type=int, default=50)
    parser.add_argument("--max-score", type=int, default=69)
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run, min_score=args.min_score, max_score=args.max_score)
