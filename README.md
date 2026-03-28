# ToolRank

**Score and optimize how AI agents discover, select, and use your tools.**

ToolRank is the first ATO (Agent Tool Optimization) platform. It measures your MCP tool definitions across four dimensions — Findability, Clarity, Precision, and Efficiency — and gives you specific fixes to get selected more often.

Research shows **97.1% of MCP tool descriptions have quality defects**, and optimized tools get selected **3.6x more often** (72% vs 20% baseline).

## Quick Start

**Web:** Visit [toolrank.dev/score](https://toolrank.dev/score) and paste your tool JSON.

**MCP Server:** Add to your MCP client config:
```json
{
  "mcpServers": {
    "toolrank": {
      "command": "npx",
      "args": ["@toolrank/mcp-server"]
    }
  }
}
```

## ToolRank Score (0-100)

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Findability | 25% | Registry presence, tags, llms.txt |
| Clarity | 35% | Description quality, purpose, usage context |
| Precision | 25% | Schema types, enums, required fields |
| Efficiency | 15% | Token cost, tool count, naming |

## ATO Framework

ATO (Agent Tool Optimization) is to the agent economy what SEO was to the search economy. Three stages: be recognized (LLMO), be selected (ATO core), be used reliably (ATO depth). Full docs at [toolrank.dev/framework](https://toolrank.dev/framework).

## Transparency

Scoring logic (Level A and B) is fully open source. See `packages/scoring/`.

## License

MIT. Copyright 2026 Taizendo Inc.
