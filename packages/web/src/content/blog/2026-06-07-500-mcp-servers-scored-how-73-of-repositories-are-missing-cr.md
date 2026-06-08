---
title: "500 MCP Servers Scored: How 73% of Repositories Are Missing Critical Tool Definitions"
description: "Analysis of 4,000+ MCP repositories reveals a stark reality: most lack the tool definitions needed for AI agent discovery."
date: "2026-06-07"
---

The MCP ecosystem has reached a significant milestone this week with **500 servers** now scored on [ToolRank](https://toolrank.dev), but the numbers reveal a concerning trend that MCP developers can't afford to ignore.

## Ecosystem Health: Strong but Selective

Our latest scan of 4,000+ repositories from the Smithery and Official MCP Registry shows remarkable quality among scored servers, with an **average score of 91.7/100**. Even more striking: **100% of scored servers fall into the "Dominant" category (85+ points)**, with zero servers in the Preferred (70-84) or Selectable (50-69) ranges.

This perfect distribution isn't a sign of grade inflation—it's a reflection of selection bias. Only repositories with well-defined tool schemas make it through our scoring algorithm. The real story lies in what doesn't get scored.

## The Hidden Crisis: 73% of MCP Repositories Lack Tool Definitions

Here's the number that should concern every MCP developer: **approximately 73% of scanned repositories have no tool definitions**. Out of 4,000+ repositories examined, only 500 contain the structured tool schemas required for AI agent discovery.

This means nearly three-quarters of MCP projects are essentially invisible to AI agents browsing for capabilities. They might contain brilliant functionality, but without proper tool definitions, they're like libraries with no catalog system.

## Top Performers Setting the Standard

Leading the pack this week:

- **URL Scanner Online by Aprensec** (97/100) - Demonstrates perfect discoverability scoring
- **Docfork** projects (96/100) - Multiple repositories showing consistent quality
- **Microsoft Learn MCP** (96/100) - Enterprise-grade tool definition practices

The scoring breakdown (F:25 C:34 P:22-23 E:15) shows these top performers excel across all dimensions: Findability, Clarity, Precision, and Examples. Notably, the slight variation in Precision scores (22-23) suggests even top-tier tools have room for optimization.

## What This Means for MCP Developers

### 1. Tool Definition is Make-or-Break

If you're among the 73% without proper tool definitions, your MCP server might as well not exist for AI agent discovery. The data shows there's no middle ground—servers either score well (85+) or don't score at all.

**Action Item**: Audit your `tools` section in your MCP configuration. Use [ToolRank's scoring system](https://toolrank.dev/score) to identify gaps before deploying.

### 2. Quality Standards Are Rising

The fact that all scored servers achieve 85+ points indicates the ecosystem is self-selecting for quality. As AI agents become more sophisticated in tool selection, only well-documented tools will see adoption.

**Action Item**: Study the top performers' tool definitions. Notice how Microsoft Learn and Docfork structure their schemas—these aren't accidents but deliberate choices that maximize discoverability.

### 3. Competition is About Clarity, Not Features

The narrow score range (90-97) among hundreds of servers proves that having more tools isn't the differentiator—having clearly defined, well-documented tools is. The 7-point spread between top and bottom performers often comes down to example quality and parameter precision.

## The Bottom Line for Developers

With 500 servers now in the "Dominant" tier, the bar for MCP tool discoverability has never been higher. The ecosystem isn't suffering from low-quality tools—it's suffering from invisible tools.

If you're building MCP servers, focus on:

1. **Complete tool schemas** - Don't ship without them
2. **Comprehensive examples** - Top scorers average 15/15 on examples
3. **Precise parameter definitions** - The difference between 22 and 23 precision points often determines ranking

The 73% of repositories without tool definitions represent both a problem and an opportunity. For developers who invest in proper tool documentation, the path to the top 500 is clear. For those who don't, their tools will remain in the undiscoverable majority.

Check your current tool definition quality at [toolrank.dev/score](https://toolrank.dev/score) and see how you rank against the 500 servers setting the standard for AI agent discoverability.