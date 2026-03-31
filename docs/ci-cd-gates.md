# ToolRank CI/CD Trust Gate

## Three-Stage Deployment Gates

ToolRank provides deployment gates that go beyond scoring — they **block untrusted MCP servers from reaching production**.

### Stage 1: Pre-Merge (Schema & Description)

Runs on every PR. Checks spec quality before code merges.

```yaml
name: ToolRank Pre-Merge Gate
on: [pull_request]

jobs:
  toolrank:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: imhiroki/toolrank-action@v2
        with:
          mode: pre-merge
          min-score: 70
          server-path: ./src/mcp-server
```

**Checks:**
- Tool descriptions are clear and complete
- Parameter schemas are valid and typed
- Error responses are defined
- No breaking changes to tool interface

### Stage 2: Pre-Release (Selection Benchmark)

Runs before release. Verifies that agents actually **choose** this tool.

```yaml
name: ToolRank Pre-Release Gate
on:
  push:
    tags: ['v*']

jobs:
  toolrank:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: imhiroki/toolrank-action@v2
        with:
          mode: pre-release
          min-score: 80
          min-selection-rate: 60
          toolrank-api-key: ${{ secrets.TOOLRANK_API_KEY }}
```

**Checks:**
- All pre-merge checks
- Selection win rate ≥ threshold (tested via LLM tournament)
- Tool is competitive in its category

### Stage 3: Post-Deploy (Trust Verification)

Runs after deployment. Ensures trust tier is maintained.

```yaml
name: ToolRank Post-Deploy Check
on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am

jobs:
  toolrank:
    runs-on: ubuntu-latest
    steps:
      - uses: imhiroki/toolrank-action@v2
        with:
          mode: post-deploy
          manifest-url: https://your-server.com/.well-known/mcp.json
          toolrank-api-key: ${{ secrets.TOOLRANK_API_KEY }}
```

**Checks:**
- Trust level ≥ 1 (at least Spec Verified)
- No tier expirations
- No score regressions

## Policy Configuration

Create `.toolrank.yml` in your repo root:

```yaml
# .toolrank.yml
gates:
  pre-merge:
    min-score: 70
    fail-on-warning: false
    
  pre-release:
    min-score: 80
    min-selection-rate: 60
    
  post-deploy:
    min-trust-level: 1
    alert-on-regression: true
    
notifications:
  slack-webhook: ${{ secrets.SLACK_WEBHOOK }}
  
ignore:
  - "test/**"
  - "examples/**"
```

## Trust API Integration

Query trust status programmatically:

```bash
# Get trust profile
curl https://toolrank.dev/api/trust-status/YOUR_SERVER_ID

# Get trusted list for a category
curl "https://toolrank.dev/api/trusted-list.json?category=filesystem&min_trust=2"

# Embed badge in README
![ToolRank Trust](https://toolrank.dev/api/trust-badge/YOUR_SERVER_ID.svg)
```

## FAQ

**Q: How is the selection win rate calculated?**
A: We run 100 rounds where Claude Sonnet picks the best tool from 4 candidates for realistic tasks. Your win rate = rounds won / rounds appeared.

**Q: What happens if my score drops after deployment?**
A: In `post-deploy` mode, a score regression triggers a warning. If your trust tier expires, the gate fails.

**Q: Can I run selection tests locally?**
A: Yes, with a ToolRank Pro API key:
```bash
curl -X POST https://mcp.toolrank.dev/api/tournament \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"server_id": "YOUR_SERVER_ID", "rounds": 50}'
```
