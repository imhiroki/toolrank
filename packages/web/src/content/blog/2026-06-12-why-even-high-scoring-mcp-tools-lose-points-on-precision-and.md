---
title: "Why Even High-Scoring MCP Tools Lose Points on Precision (and the 10-Second Fix)"
description: "Analysis of 500 MCP servers reveals subtle precision issues costing developers discovery points—here's the exact fix."
date: "2026-06-12"
---

The MCP ecosystem has reached an impressive milestone: all 500 scored servers on [ToolRank](https://toolrank.dev) now achieve "Dominant" status (85+ points), with an average score of 91.7/100. Yet even among these high performers, there's a consistent pattern of lost points that could be easily prevented.

After analyzing the scoring breakdown across all servers, the most common optimization opportunity isn't in the obvious areas like descriptions or examples—it's in **precision scoring**, where even top-tier tools are leaving points on the table.

## The Precision Problem: Small Details, Big Impact

Looking at the top 10 servers, precision scores range from 22-23 out of 25 points. While these are strong scores, they represent the most variable component across high-performing tools. Compare this to findability (consistently 25/25) or clarity (33-34/35), and you'll see precision is where optimization opportunities remain.

The precision score measures how well your tool definitions target specific use cases rather than being overly broad. AI agents rely on this specificity to determine when to invoke your tool versus alternatives.

## Before and After: The Parameter Precision Fix

Here's a realistic example based on common patterns in the scored servers:

**Before (loses 2-3 precision points):**
```json
{
  "name": "search_documents",
  "description": "Search for documents",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query"
      },
      "limit": {
        "type": "number",
        "description": "Number of results"
      }
    },
    "required": ["query"]
  }
}
```

**After (gains full precision points):**
```json
{
  "name": "search_documents",
  "description": "Search through document content using full-text search with relevance ranking",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search terms or phrases to find in document content. Supports boolean operators (AND, OR, NOT) and quoted phrases for exact matches.",
        "minLength": 1,
        "maxLength": 200
      },
      "limit": {
        "type": "number",
        "description": "Maximum number of documents to return, ranked by relevance score",
        "minimum": 1,
        "maximum": 100,
        "default": 10
      }
    },
    "required": ["query"]
  }
}
```

The key differences driving higher precision scores:

1. **Specific description scope**: "full-text search with relevance ranking" vs. generic "search"
2. **Detailed parameter guidance**: Explaining boolean operators and phrase matching capabilities
3. **Practical constraints**: Min/max values that reflect real-world usage limits
4. **Default values**: Reducing cognitive load for AI agents

## Why Precision Matters for AI Agent Selection

When an AI agent faces multiple tools that could handle a user request, precision scoring directly impacts selection probability. Consider a scenario where a user asks to "find my recent expense reports."

An agent choosing between these tools:
- `search_documents` (22/25 precision): Generic search capability
- `find_expense_reports` (25/25 precision): Specifically designed for financial document retrieval

The higher-precision tool wins because its parameters and description clearly indicate specialized functionality. The agent can confidently predict that invoking it will produce more relevant results.

This selection bias compounds over time. Tools with lower precision scores get invoked less frequently, reducing their effective value despite potentially superior underlying functionality.

## The 10-Second Fix: Parameter Constraints

The fastest way to boost your precision score is adding realistic constraints to your parameters:

1. **Add min/max lengths** to string parameters
2. **Set numerical ranges** that reflect actual usage
3. **Include default values** for optional parameters
4. **Specify formats** for structured inputs (dates, emails, etc.)

For example, changing:
```json
"date": {
  "type": "string",
  "description": "Date to search"
}
```

To:
```json
"date": {
  "type": "string",
  "description": "Date to search in ISO 8601 format (YYYY-MM-DD)",
  "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
  "example": "2026-06-12"
}
```

This single change can increase your precision score by 1-2 points, moving you closer to the perfect 25/25 achieved by only the most meticulously crafted tools.

## The Compound Effect of Precision Optimization

With 4,000+ repositories scanned and only 500 containing scoreable tool definitions, the MCP ecosystem is still emerging. Developers who optimize for precision now position their tools for better discoverability as the ecosystem grows and AI agents become more sophisticated in their selection algorithms.

The servers consistently scoring 96-97/100 share one trait: obsessive attention to parameter precision. They treat every property description, constraint, and example as an opportunity to communicate intent clearly to AI agents.

## Next Steps

Check your current precision score at [toolrank.dev/score](https://toolrank.dev/score). If you're scoring below 23/25 on precision, review your parameter definitions for missing constraints and examples. The top-performing servers prove that achieving 25/25 precision is attainable—and the compound benefits for AI agent selection make the optimization effort worthwhile.

Remember: in an ecosystem where 73% of repositories lack tool definitions entirely, the difference between good and great precision scoring can determine whether your tools get discovered and used.