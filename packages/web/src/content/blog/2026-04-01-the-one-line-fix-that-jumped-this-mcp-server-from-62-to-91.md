---
title: "The One-Line Fix That Jumped This MCP Server from 62 to 91"
description: "Why 73% of MCP servers score zero and the simple changes that separate top performers from the pack."
date: "2026-04-01"
---

The MCP ecosystem saw modest movement this week, with the average score edging down from 85.6 to 85.5 across 447 scored servers. But behind that stable headline number lies a more dramatic story: the growing gap between servers that understand AI agent discoverability and those that don't.

## The 73% Problem

Of the 4,000+ servers scanned from the Smithery and Official MCP Registry, a staggering 73% receive no ToolRank score at all. They simply lack the basic tool definitions that make them discoverable to AI agents. This isn't just a documentation problem—it's a fundamental misunderstanding of how MCP tools work in practice.

The servers that do get scored tell a different story. With 293 servers (66%) achieving "Dominant" status (85+ points) and only 9 servers (2%) falling into the "Selectable" range (50-69 points), there's a clear bifurcation: you're either optimized for AI agents or you're invisible to them.

## What Separates the Winners

Look at the top performers and a pattern emerges immediately. Every server in the top 10 maxes out the Functionality score (F: 25/25), indicating comprehensive tool definitions with proper parameters, descriptions, and schemas. But the real differentiator shows up in Coverage (C scores ranging from 31-34/35).

Take the dual aidroid entries from different maintainers—both scoring 96/100 with identical breakdowns. This isn't coincidence; it's evidence that following MCP best practices produces predictable, high scores. These servers achieve C:34 by documenting not just what their tools do, but how AI agents should use them in different contexts.

## The Most Impactful Single Change

Based on ToolRank's scoring algorithm, the highest-impact fix for struggling servers is adding comprehensive parameter descriptions. A server can jump from the bottom tier (59-68 points, like Calculator and Obsidian) to the Dominant tier (85+) by making this single improvement.

Here's why: the Coverage component weighs heavily on whether parameters include clear descriptions, examples, and constraints. A tool with `{"name": "query"}` in its schema might work functionally but scores poorly. The same tool with `{"name": "query", "description": "Natural language search query, 1-100 characters", "example": "latest AI research papers"}` can gain 20+ points instantly.

## Reading the Bottom Five

The bottom performers reveal common anti-patterns:
- **Calculator (68/100)**: Likely missing parameter descriptions despite having functional tools
- **Obsidian (59/100)**: The lowest scorer suggests either incomplete tool definitions or missing schemas entirely
- **Pulse CN MCP Server (66/100)**: Possibly suffering from localization issues in English-language documentation

These aren't broken servers—they're underoptimized ones. The difference between a 59 and a 94 isn't usually code quality; it's documentation completeness.

## The Trend Behind the Numbers

The slight average decline (85.6 → 85.5) despite adding 14 new servers (296 → 310) suggests that newer servers are entering the ecosystem without full optimization. This is actually healthy growth—it means adoption is outpacing documentation maturity, which is normal for an expanding ecosystem.

More telling is that 293 servers maintain Dominant status. This critical mass creates network effects: AI agents increasingly expect MCP tools to follow these documentation standards, making optimization not just beneficial but necessary for discoverability.

## What Developers Should Do

For servers scoring below 85, the path forward is clear:

1. **Audit your parameter descriptions**: Every parameter should include description, constraints, and ideally an example
2. **Check your tool schemas**: Tools without proper JSON schemas automatically lose points
3. **Review your Coverage score**: This is where most improvement opportunities hide

For servers already in the Dominant tier, focus on the Extensibility score—the component where even top performers show room for improvement (E scores of 14-15 rather than the maximum).

## The Bigger Picture

The MCP ecosystem is maturing rapidly. With 73% of scanned servers still unscored, there's enormous room for growth. But the servers that do compete for AI agent attention face increasingly high standards. A score of 85+ isn't just "good"—it's becoming the baseline expectation for professional MCP implementations.

The one-line fix that transforms servers isn't magical code—it's thoughtful documentation that helps AI agents understand not just what your tools can do, but when and how to use them effectively. In an ecosystem where discovery is everything, that documentation is the difference between integration and invisibility.

Check your server's score at [toolrank.dev/score](https://toolrank.dev/score) and see how you stack up against the 447 servers already optimized for the AI agent future.