<div align="center">

# ToolRank

### The PageRank for AI agent tools.

**Score, optimize, and monitor how AI agents discover and select your MCP tools.**

[![ToolRank Score](https://img.shields.io/badge/ToolRank-96%2F100-6d28d9?style=flat-square)](https://toolrank.dev/score)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-Scoring%20Engine-blue?style=flat-square)](https://github.com/imhiroki/toolrank/tree/main/packages/scoring)

[**Score Your Tools →**](https://toolrank.dev/score) · [Framework](https://toolrank.dev/framework) · [Ranking](https://toolrank.dev/ranking) · [Blog](https://toolrank.dev/blog)

</div>

---

## We scanned 4,162 MCP servers. Here's what we found.

| Metric | Value |
|--------|-------|
| **Registered servers** | 4,162 |
| **With tool definitions** | 1,122 (27%) |
| **Invisible to agents** | 3,040 (73%) |
| **Average score** | 84.7/100 |
| **Selection advantage** | 3.6x for optimized tools |

> **73% of MCP servers are invisible to AI agents.** They have no tool definitions, no descriptions, no schema. When an agent searches for tools, these servers don't exist.

Sources: [arXiv 2602.14878](https://arxiv.org/abs/2602.14878), [arXiv 2602.18914](https://arxiv.org/abs/2602.18914)

## What is ATO?

**ATO (Agent Tool Optimization)** is to the agent economy what SEO was to the search economy.

| | SEO | LLMO | ATO |
|---|-----|------|-----|
| **Target** | Search engines | LLM responses | Agent tool selection |
| **Trigger** | Human searches | Human asks AI | Agent acts autonomously |
| **Result** | A click | A mention | A transaction |

LLMO is Stage 1 of ATO — necessary but not sufficient.

## Quick Start

### Score in browser
[**toolrank.dev/score**](https://toolrank.dev/score) — paste your tool JSON or enter your Smithery server name.

### Score via CLI
```bash
npx @toolrank/mcp-server
```

### Score in Python
```python
from toolrank_score import score_server, format_report

result = score_server("my-server", tools)
print(format_report(result))
```

## ToolRank Score

0-100 metric across four dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **Findability** | 25% | Can agents discover you? |
| **Clarity** | 35% | Can agents understand you? |
| **Precision** | 25% | Is your schema precise? |
| **Efficiency** | 15% | Are you token-efficient? |

### Maturity Levels

| Level | Score | Meaning |
|-------|-------|---------|
| Dominant | 85-100 | Agents prefer your tool |
| Preferred | 70-84 | Agents can use your tool well |
| Selectable | 50-69 | Agents might use your tool |
| Visible | 25-49 | Agents see you but rarely select |
| Absent | 0-24 | Agents can't find you |

## Before and After

```diff
- "name": "get",
- "description": "gets data from the api"
+ "name": "search_repositories",
+ "description": "Searches for GitHub repositories matching a query.
+   Useful for finding open-source projects or checking if a repo exists.
+   Returns name, description, stars, language, and URL.",
+ "inputSchema": {
+   "type": "object",
+   "properties": {
+     "query": { "type": "string", "description": "Search query" },
+     "sort": { "type": "string", "enum": ["stars", "forks", "updated"] }
+   },
+   "required": ["query"]
+ }
```

**Score: 52 → 96.** Five minutes of work. 3.6x selection advantage.

## Architecture

```
toolrank/
├── packages/
│   ├── scoring/           # Level A engine (Python, zero-cost)
│   │   ├── toolrank_score.py    # 14 checks across 4 dimensions
│   │   ├── level_c_score.py     # Claude AI scoring (Pro)
│   │   └── weights.json         # Auto-calibrated weights
│   ├── scanner/           # Ecosystem scanner
│   │   ├── scanner_v3.py        # Weekly full / daily diff
│   │   ├── calibrate.py         # Weight auto-adjustment
│   │   └── auto_blog.py         # Daily article generation
│   ├── web/               # Astro site (toolrank.dev)
│   ├── mcp-server/        # ToolRank MCP Server
│   └── badge-worker/      # Dynamic badge SVG (CF Workers)
└── .github/workflows/     # Automated pipelines
```

## Ecosystem Rankings

Updated weekly. [Full ranking →](https://toolrank.dev/ranking)

| Rank | Server | Score |
|------|--------|-------|
| 1 | microsoft/learn_mcp | 96.5 |
| 2 | docfork/docfork | 96.5 |
| 3 | brave | 94.7 |
| 4 | LinkupPlatform/linkup-mcp-server | 93.5 |
| 5 | smithery-ai/national-weather-service | 93.3 |

## Add Badge to Your README

```markdown
[![ToolRank](https://toolrank.dev/badge/dominant.svg)](https://toolrank.dev/ranking)
```

## Contributing

ToolRank is open source. The scoring logic is fully transparent and auditable.

- **Report issues:** [GitHub Issues](https://github.com/imhiroki/toolrank/issues)
- **Scoring methodology:** [packages/scoring/toolrank_score.py](packages/scoring/toolrank_score.py)
- **ATO Framework:** [toolrank.dev/framework](https://toolrank.dev/framework)

## License

MIT

---

<div align="center">

**[toolrank.dev](https://toolrank.dev)** · Built by [@imhiroki](https://github.com/imhiroki)

*If SEO is about being found by search engines, ATO is about being used by AI agents.*

</div>
