---
title: "The 89-Point Floor: Why No MCP Server Scores Below 89 Anymore"
description: "Analysis of the dramatic compression in ToolRank scores reveals what developers are finally getting right about MCP tool definitions."
date: "2026-04-29"
---

Something remarkable has happened in the MCP ecosystem: the worst-performing server now scores 89 out of 100. Just months ago, we tracked servers struggling in the 60s and 70s. Today, all 500 scored servers cluster between 89-97 points, creating an unprecedented quality floor.

## The Great Score Compression

The data tells a striking story. Our ecosystem has compressed into what we're calling the "Dominant Zone" - every single server now scores 85 or above, with the bottom 5 servers (Gmail, Agent Payments Intelligence, KMB Bus, Resume Optimizer Pro, and Octomil) all sitting at exactly 89 points.

This represents a fundamental shift from the typical bell curve distribution we see in most software quality metrics. Instead of servers scattered across performance tiers, we now see:

- **500 servers** in the Dominant tier (85+)
- **0 servers** in Preferred (70-84) or Selectable (50-69) tiers
- **Average score**: 91.6/100, up from our previous 86.4

The ecosystem average jumped 0.3 points despite having 33 fewer servers (267 → 234), indicating that poorly-performing servers are either improving dramatically or disappearing entirely.

## What's Driving the Quality Floor

The score breakdown of our top performers reveals the pattern. Take the URL Scanner Online server at 97 points: F:25 C:34 P:22 E:15. Every high-scoring server shows similar distribution across our four core metrics:

- **Functionality (F)**: Consistently maxed at 25/25
- **Clarity (C)**: Strong performance around 34/35  
- **Parameters (P)**: Solid 22-23 range
- **Examples (E)**: The differentiator at 15/15

The bottom-tier servers at 89 points are losing ground primarily in the Parameters and Examples categories. This suggests developers have mastered the fundamentals of tool definition structure but struggle with comprehensive parameter documentation and practical examples.

## The Most Impactful Single Change

Based on our analysis of score patterns, the single most impactful change a developer can make is **adding comprehensive parameter examples**. The 8-point gap between our top performers (97) and bottom tier (89) consistently correlates with example quality.

Servers scoring 96-97 points universally provide:
- Real-world parameter examples for each tool function
- Edge case handling documentation  
- Clear input/output format specifications
- Error scenario examples

Meanwhile, 89-point servers typically have complete tool definitions but sparse or generic examples. This 8-point difference can mean the difference between an AI agent confidently using your tool versus hesitating due to uncertainty about proper parameter formatting.

## The Disappearing Middle Tier

Perhaps most telling is what we don't see: no servers scoring between 70-84 points. This suggests the MCP community has reached a maturity inflection point where developers either implement comprehensive tool definitions correctly or don't publish at all.

The 73% of scanned servers with no tool definitions (from our 4,000+ total scan) supports this theory. Rather than publishing incomplete definitions, developers appear to be waiting until they can meet the quality bar.

## Framework Winners and Losers

Looking at our top 10, we see clear framework patterns. Microsoft's official Learn MCP implementations occupy multiple top spots, while community-driven servers like Toolrank, Docfork, and various aidroid implementations also achieve 96-point scores.

Notably absent from the top tier are some traditionally popular categories. Productivity tools and data connectors, once dominant in MCP catalogs, now struggle to differentiate through superior tool definitions rather than just functionality.

## What This Means for Developers

This quality compression creates both opportunity and pressure:

**The Opportunity**: With such high baseline quality, small improvements have outsized impact. Moving from 89 to 94 points can dramatically improve your tool's discoverability in AI agent selection algorithms.

**The Pressure**: The days of "good enough" tool definitions are over. Agents have hundreds of high-quality options, making comprehensive documentation and examples non-negotiable.

## Actionable Takeaways

For developers looking to break into the top tier:

1. **Audit your examples**: Can an AI agent understand exactly how to format parameters from your documentation alone?

2. **Test edge cases**: Document what happens when parameters are missing, malformed, or outside expected ranges

3. **Show, don't just tell**: Include actual JSON examples rather than parameter descriptions

4. **Benchmark against leaders**: Compare your tool definition against the 96-97 point servers in our [ranking](https://toolrank.dev/ranking)

The 89-point floor represents a new baseline for MCP tool quality. Developers who embrace comprehensive documentation won't just score higher - they'll build tools that AI agents actually want to use.

Check your current tool's score at [toolrank.dev/score](https://toolrank.dev/score) to see where you stand in this increasingly competitive landscape.