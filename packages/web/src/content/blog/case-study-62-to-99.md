---
title: "Case study: From 69 to 99 in 5 minutes — optimizing our own MCP server"
description: "We applied ToolRank's own framework to our MCP server. Score jumped from 69.7 to 99.0 with zero code changes. Here's exactly what we changed and why it works."
date: "2026-03-29"
author: "Hiroki Honda"
---

We tell people to optimize their MCP tool definitions. So we did it to our own server first.

## The experiment

We took a deliberately bad version of the ToolRank MCP Server — short names, vague descriptions, no parameter docs — and scored it. Then we applied the ATO framework fixes and scored again.

No code changes. No new features. Just better text.

## Before: 69.7/100 (Selectable)

```json
{
  "name": "score",
  "description": "scores tools",
  "inputSchema": {
    "type": "object",
    "properties": {
      "tools": { "type": "array" }
    }
  }
}
```

**Score: 69.7/100 — Selectable tier**

| Dimension | Score | Max |
|-----------|-------|-----|
| Findability | 15.0 | 25 |
| Clarity | 22.0 | 35 |
| Precision | 17.7 | 25 |
| Efficiency | 15.0 | 15 |

**8 issues detected per tool (16 total):**
- Description too short (12 chars)
- No action verb
- No usage context
- No return value described
- No parameter descriptions
- No required fields defined
- Name too generic ("score" could be anything)
- Name-description keyword mismatch

An agent seeing this tool alongside 5 competitors has no reason to pick it. "Scores tools" tells the agent nothing about what kind of tools, what dimensions, or what the output looks like.

## After: 99.0/100 (Dominant)

```json
{
  "name": "toolrank_score",
  "description": "Analyzes MCP tool definitions and returns a ToolRank Score (0-100) measuring agent-readiness. Evaluates four dimensions: Findability (25%), Clarity (35%), Precision (25%), and Efficiency (15%). Use this when you want to check or improve the quality of your MCP tool definitions. Returns per-tool scores, maturity level, specific issues found, and fix suggestions ranked by impact.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "tools": {
        "type": "array",
        "description": "Array of MCP tool definition objects. Each must have name and description fields.",
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string", "description": "Tool name" },
            "description": { "type": "string", "description": "Tool description" },
            "inputSchema": { "type": "object", "description": "JSON Schema" }
          },
          "required": ["name", "description"]
        }
      }
    },
    "required": ["tools"]
  }
}
```

**Score: 99.0/100 — Dominant tier**

| Dimension | Before | After | Change |
|-----------|--------|-------|--------|
| Findability | 15.0 | 25.0 | +10.0 |
| Clarity | 22.0 | 34.0 | +12.0 |
| Precision | 17.7 | 25.0 | +7.3 |
| Efficiency | 15.0 | 15.0 | — |

**0 issues. Perfect score on all dimensions except 1 point of clarity.**

## What changed

Seven specific changes, each taking under a minute:

1. **Name: `score` → `toolrank_score`** — Descriptive, searchable, domain-specific. An agent searching for "tool scoring" or "MCP quality" will find this. (+4pt Findability)

2. **Description: 12 chars → 283 chars** — From "scores tools" to a complete sentence with purpose, methodology, context, and return value. (+12pt Clarity)

3. **Added action verb** — "Analyzes" at the start. Agents parse the first word to categorize tools. (+2pt Clarity)

4. **Added usage context** — "Use this when you want to check or improve the quality of your MCP tool definitions." Agents need this to decide between competing tools. (+4pt Clarity)

5. **Added return description** — "Returns per-tool scores, maturity level, specific issues found, and fix suggestions ranked by impact." Agents need to know what they'll get back. (+3pt Clarity)

6. **Added parameter descriptions** — Every property has a `description` field explaining what it expects. (+5pt Precision)

7. **Added required fields** — `"required": ["tools"]` tells agents which parameters are mandatory. (+3pt Precision)

## The math

Research (arXiv 2602.18914) shows quality-compliant tools achieve 72% selection probability versus 20% for non-compliant. That's 3.6x.

A "Selectable" tool at 69.7 is in the non-compliant range. A "Dominant" tool at 99.0 is firmly in the compliant range.

Same functionality. Same API. Same code. The only difference is how you describe it.

## Try it yourself

1. **Score your tools:** [toolrank.dev/score](https://toolrank.dev/score)
2. **Fix the top issues** — the tool shows exactly what to change
3. **Copy the rewrite** — the suggested rewrite is ready to paste
4. **Score again** — verify the improvement

Five minutes. Zero code changes. Measurable advantage.

---

*Full ranking: [toolrank.dev/ranking](https://toolrank.dev/ranking). Open source: [github.com/imhiroki/toolrank](https://github.com/imhiroki/toolrank).*
