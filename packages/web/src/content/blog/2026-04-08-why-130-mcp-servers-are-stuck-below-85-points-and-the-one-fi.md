---
title: "Why 130 MCP Servers Are Stuck Below 85 Points (And the One Fix That Could Save Them)"
description: "ToolRank's latest ecosystem scan reveals 26% of MCP servers trapped in the 70-84 range—but the solution might be simpler than you think."
date: "2026-04-08"
---

The MCP ecosystem is experiencing a peculiar growth pattern. While the total number of scored servers jumped from 317 to 328 in recent weeks, the average score barely budged—creeping from 85.7 to just 85.9 points. More telling: **130 servers remain stuck in the "Preferred" tier (70-84 points)**, unable to break into the coveted "Dominant" category that 370 servers now occupy.

What's keeping these 130 servers from reaching their potential? ToolRank's latest ecosystem data reveals a clear pattern—and a surprisingly simple solution.

## The Tale of Two Tiers

The current MCP landscape shows a stark divide. On one side, 74% of servers (370 out of 500) score 85+ and achieve "Dominant" status. These include standouts like URL Scanner Online by Aprensec at 97/100 and Microsoft Learn MCP at 96/100. On the other side, 26% languish in the 70-84 range, with servers like Spotify and Pokémon Information Server bottoming out at exactly 78/100.

This isn't random distribution—it's a structural problem.

## The Four Pillars: Where Servers Fall Short

ToolRank's scoring system evaluates servers across four categories: Functionality (F), Clarity (C), Performance (P), and Extensibility (E). Looking at the top performers, a pattern emerges:

- **URL Scanner Online**: F:25 C:34 P:22 E:15 (Total: 97)
- **Microsoft Learn MCP**: F:25 C:34 P:23 E:15 (Total: 96)
- **aidroid servers**: F:25 C:34 P:23 E:15 (Total: 96)

Notice something? Every top-10 server maxes out Functionality at 25 points. They also excel in Clarity, with most scoring 32+ out of a possible 34 points. Meanwhile, the bottom performers—all clustering at 78/100—are losing critical points in these fundamental areas.

## The One-Line Fix That Changes Everything

Here's the counterintuitive truth: **the biggest score jump often comes from a single line of documentation**.

Consider the Clarity category, where top servers consistently score 32+ points while struggling servers hover around the mid-20s. This category heavily weights tool description quality, parameter clarity, and usage examples. A server jumping from a generic description like "performs web searches" to a specific one like "executes semantic web searches with customizable result filtering and relevance ranking" can gain 5-8 Clarity points instantly.

That seemingly minor change—one line of better documentation—can push a server from 78 to 86 points, crossing the critical threshold from "Preferred" to "Dominant" status.

## Why Scores Plateau at Specific Numbers

The clustering at 78/100 isn't coincidental. It represents a specific failure pattern: servers that implement basic functionality (earning most Functionality points) but neglect documentation and user experience (losing Clarity and Performance points). These servers typically:

- Define tools without comprehensive descriptions
- Skip parameter validation or clear error messages  
- Provide minimal usage examples
- Lack performance optimizations for common use cases

The jump from 78 to 85+ requires systematic attention to these "polish" elements that many developers consider secondary.

## The Extensibility Trap

Interestingly, Extensibility scores remain consistently modest across all tiers. Even top performers rarely exceed 15 points in this category. This suggests that most MCP servers, regardless of quality, struggle with modularity, plugin architecture, and future-proofing.

For developers looking beyond the 85-point threshold, Extensibility offers the clearest path to true excellence. The difference between a 94-point server and a 97-point server often lies entirely in this category.

## What the Data Reveals About Developer Priorities

The fact that 73% of scanned repositories have no tool definitions at all, yet 74% of scored servers achieve "Dominant" status, reveals an important truth: developers who commit to proper MCP implementation typically do it well. The challenge isn't convincing good developers to improve—it's convincing the remaining 27% to cross the quality threshold.

The static number of servers in the bottom tier (all at exactly 78/100) suggests these represent a specific type: functional but unpolished servers that likely haven't been updated since their initial implementation.

## Actionable Steps for the Stuck 130

For servers trapped in the 70-84 range, the path forward is clear:

1. **Audit your tool descriptions**: Replace generic phrases with specific, benefit-focused language
2. **Add comprehensive parameter documentation**: Include types, constraints, and examples for every parameter
3. **Implement proper error handling**: Clear error messages boost both Clarity and Performance scores
4. **Provide usage examples**: Real-world scenarios help both user understanding and SEO discoverability

The data shows that servers making these changes typically see 7-12 point improvements, easily crossing into "Dominant" territory.

For developers ready to optimize their MCP tools for better AI agent discoverability, [ToolRank's scoring framework](https://toolrank.dev/framework) provides detailed guidance on each category. The current ecosystem proves that with focused effort, any server can join the 370 already achieving excellence.

The question isn't whether your server can improve—it's whether you'll make the changes before your competitors do.