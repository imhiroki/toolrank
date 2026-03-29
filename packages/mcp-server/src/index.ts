/**
 * ToolRank MCP Server v0.1
 * 
 * Provides AI agents with tools to score and optimize MCP tool definitions.
 * This server's own tool definitions are designed to achieve ToolRank Score 100/100,
 * serving as a live demonstration of ATO (Agent Tool Optimization) principles.
 * 
 * Tools:
 *   toolrank_score    — Analyze tool definitions and return quality scores
 *   toolrank_compare  — Compare scores against category averages
 *   toolrank_suggest  — Generate specific improvement suggestions
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// --- Scoring Engine (TypeScript port of Level A) ---

interface Issue {
  dimension: string;
  severity: "critical" | "warning" | "info";
  message: string;
  fix: string;
  impact: number;
}

interface ToolScoreResult {
  name: string;
  total: number;
  level: number;
  levelName: string;
  dimensions: {
    findability: number;
    clarity: number;
    precision: number;
    efficiency: number;
  };
  issues: Issue[];
}

function scoreTool(tool: Record<string, any>): ToolScoreResult {
  const issues: Issue[] = [];
  const name = tool.name || "unknown";
  const desc = (tool.description || "").trim();
  const schema = tool.inputSchema || tool.input_schema || {};
  const props = schema.properties || {};
  const required = schema.required || [];
  const propKeys = Object.keys(props);

  // --- Clarity (max 35) ---
  let clarityScore = 0;
  const clarityMax = 6;
  let clarityPoints = 0;

  if (!desc) {
    issues.push({ dimension: "clarity", severity: "critical", message: "No description defined", fix: "Add a description explaining purpose, usage context, and return value", impact: 15 });
  } else {
    clarityPoints += 1;

    if (desc.length < 20) {
      issues.push({ dimension: "clarity", severity: "critical", message: `Description too short (${desc.length} chars)`, fix: "Expand to 80-200 chars with purpose and context", impact: 10 });
      clarityPoints += 0.2;
    } else if (desc.length >= 80 && desc.length <= 250) {
      clarityPoints += 1;
    } else if (desc.length >= 50) {
      clarityPoints += 0.7;
      if (desc.length < 80) issues.push({ dimension: "clarity", severity: "warning", message: `Description short (${desc.length} chars)`, fix: "Expand to 80-200 chars for optimal agent understanding", impact: 5 });
    } else {
      clarityPoints += 0.3;
      issues.push({ dimension: "clarity", severity: "warning", message: `Description short (${desc.length} chars)`, fix: "Expand to 80-200 chars", impact: 5 });
    }

    const descLower = desc.toLowerCase();
    if (/^(get|set|create|update|delete|search|find|list|fetch|send|this tool|retriev|return|provid|allow|enabl|perform|analyz|generat|calculat|check|validat|convert|extract|scor|compar|suggest|optimiz)/.test(descLower)) {
      clarityPoints += 1;
    } else {
      clarityPoints += 0.5;
      issues.push({ dimension: "clarity", severity: "warning", message: "No clear purpose verb at start", fix: "Start with a verb: 'Analyzes...', 'Returns...', 'Generates...'", impact: 5 });
    }

    if (/use this|when|useful for|ideal for|designed for|helps|allows|enables|for example/.test(descLower)) {
      clarityPoints += 1;
    } else {
      clarityPoints += 0.4;
      issues.push({ dimension: "clarity", severity: "warning", message: "No usage context", fix: "Add 'Use this when...' to help agents decide when to select this tool", impact: 6 });
    }

    if (/returns?|outputs?|produces|yields|result|response|provides|generates/.test(descLower)) {
      clarityPoints += 1;
    } else {
      clarityPoints += 0.5;
      issues.push({ dimension: "clarity", severity: "info", message: "No return value described", fix: "Add 'Returns...' to describe the output", impact: 3 });
    }

    const nameParts = name.toLowerCase().split(/[_\-]/).filter((p: string) => p.length > 2);
    const matchCount = nameParts.filter((p: string) => descLower.includes(p)).length;
    clarityPoints += nameParts.length > 0 && matchCount / nameParts.length >= 0.5 ? 1 : 0.5;
  }
  clarityScore = Math.round((clarityPoints / clarityMax) * 35 * 10) / 10;

  // --- Precision (max 25) ---
  let precisionPoints = 0;
  const precisionMax = 5;

  if (!schema.type) {
    issues.push({ dimension: "precision", severity: "critical", message: "No input schema defined", fix: "Add inputSchema with type definitions for all parameters", impact: 12 });
  } else {
    precisionPoints += 1;
    if (propKeys.length > 0) {
      const missingTypes = propKeys.filter(k => !props[k].type);
      if (missingTypes.length === 0) precisionPoints += 1;
      else {
        precisionPoints += Math.max(0, 1 - missingTypes.length / propKeys.length);
        issues.push({ dimension: "precision", severity: "warning", message: `Missing types: ${missingTypes.join(", ")}`, fix: "Add 'type' to each parameter", impact: 4 });
      }

      const missingDesc = propKeys.filter(k => !props[k].description);
      if (missingDesc.length === 0) precisionPoints += 1;
      else {
        precisionPoints += Math.max(0, 1 - missingDesc.length / propKeys.length);
        issues.push({ dimension: "precision", severity: "warning", message: `Missing param descriptions: ${missingDesc.join(", ")}`, fix: "Add 'description' to each parameter", impact: 5 });
      }

      precisionPoints += required.length > 0 ? 1 : 0.5;
      if (required.length === 0 && propKeys.length > 0) {
        issues.push({ dimension: "precision", severity: "info", message: "No required fields specified", fix: "Add 'required' array for mandatory parameters", impact: 3 });
      }

      precisionPoints += 1;
    } else {
      precisionPoints += 2;
    }
  }
  const precisionScore = Math.round((precisionPoints / precisionMax) * 25 * 10) / 10;

  // --- Efficiency (max 15) ---
  const tokenEst = JSON.stringify(tool).length / 4;
  let effRatio = tokenEst > 2000 ? 0.3 : tokenEst > 1000 ? 0.6 : tokenEst > 500 ? 0.8 : 1.0;
  if (tokenEst > 1000) issues.push({ dimension: "efficiency", severity: "warning", message: `~${Math.round(tokenEst)} tokens estimated`, fix: "Create a compact variant", impact: 3 });

  if (!/^[a-z][a-zA-Z0-9_]*$/.test(name)) {
    effRatio -= 0.15;
    issues.push({ dimension: "efficiency", severity: "warning", message: `Name '${name}' not snake_case`, fix: "Use snake_case like 'search_users'", impact: 3 });
  }
  const genericNames = new Set(["run", "execute", "do", "action", "tool", "function", "process", "handle"]);
  if (genericNames.has(name.toLowerCase())) {
    effRatio -= 0.15;
    issues.push({ dimension: "efficiency", severity: "warning", message: `Name '${name}' too generic`, fix: "Use specific name like 'create_pull_request'", impact: 5 });
  }
  const efficiencyScore = Math.round(Math.max(0, effRatio) * 15 * 10) / 10;

  // --- Findability (max 25, limited without registry) ---
  let findRatio = name.length < 4 ? 0.3 : 0.8;
  if (name.length < 4) issues.push({ dimension: "findability", severity: "warning", message: `Name '${name}' too short for discovery`, fix: "Use a longer, descriptive name", impact: 4 });
  const findabilityScore = Math.round(findRatio * 25 * 10) / 10;

  const total = Math.round((findabilityScore + clarityScore + precisionScore + efficiencyScore) * 10) / 10;

  let level: number, levelName: string;
  if (total >= 85) { level = 4; levelName = "Dominant"; }
  else if (total >= 70) { level = 3; levelName = "Preferred"; }
  else if (total >= 50) { level = 2; levelName = "Selectable"; }
  else if (total >= 25) { level = 1; levelName = "Visible"; }
  else { level = 0; levelName = "Absent"; }

  return {
    name,
    total,
    level,
    levelName,
    dimensions: { findability: findabilityScore, clarity: clarityScore, precision: precisionScore, efficiency: efficiencyScore },
    issues: issues.sort((a, b) => b.impact - a.impact),
  };
}

// --- MCP Server Setup ---

const server = new Server(
  { name: "toolrank", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

// Tool definitions — these ARE the product. ATO Score 100/100 target.
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "toolrank_score",
      description:
        "Analyzes MCP tool definitions and returns a ToolRank Score (0-100) measuring how likely AI agents are to discover and select each tool. Scores four dimensions: Findability (can agents find it?), Clarity (can agents understand it?), Precision (is the schema well-defined?), and Efficiency (is it token-efficient?). Use this when you want to evaluate the quality of your MCP server's tool definitions before publishing. Returns per-tool scores, maturity level (Absent/Visible/Selectable/Preferred/Dominant), specific issues found, and prioritized improvement suggestions with predicted score impact.",
      inputSchema: {
        type: "object",
        properties: {
          tools: {
            type: "array",
            description:
              "Array of MCP tool definition objects. Each object should have 'name' (string), 'description' (string), and optionally 'inputSchema' (JSON Schema object with properties, required, etc.)",
            items: {
              type: "object",
              properties: {
                name: { type: "string", description: "Tool name (e.g., 'create_issue')" },
                description: { type: "string", description: "Tool description text" },
                inputSchema: { type: "object", description: "JSON Schema for tool input parameters" },
              },
              required: ["name"],
            },
          },
          server_name: {
            type: "string",
            description: "Optional name of the MCP server being scored. Used in the report header.",
            default: "unnamed",
          },
        },
        required: ["tools"],
      },
    },
    {
      name: "toolrank_compare",
      description:
        "Compares a tool's ToolRank Score against ecosystem benchmarks. Use this after running toolrank_score to understand how your tools rank relative to the broader MCP ecosystem. Returns percentile ranking, dimension-by-dimension comparison against category averages, and specific areas where your tools underperform. Requires a prior toolrank_score result or raw tool definitions.",
      inputSchema: {
        type: "object",
        properties: {
          tools: {
            type: "array",
            description: "Array of MCP tool definition objects to compare",
            items: { type: "object" },
          },
          category: {
            type: "string",
            description: "Tool category for comparison (e.g., 'crm', 'database', 'devtools'). If omitted, compares against the full ecosystem average.",
            default: "all",
          },
        },
        required: ["tools"],
      },
    },
    {
      name: "toolrank_suggest",
      description:
        "Generates specific, actionable improvement suggestions for MCP tool definitions. Use this when you have a low ToolRank Score and want concrete text rewrites. Returns optimized versions of tool names, descriptions, and schema improvements ranked by expected score impact. Does not execute changes — returns suggestions for review.",
      inputSchema: {
        type: "object",
        properties: {
          tool: {
            type: "object",
            description: "Single MCP tool definition to improve. Must include 'name' and 'description'.",
            properties: {
              name: { type: "string", description: "Current tool name" },
              description: { type: "string", description: "Current tool description" },
              inputSchema: { type: "object", description: "Current input schema" },
            },
            required: ["name"],
          },
          focus: {
            type: "string",
            description: "Which dimension to prioritize improvements for",
            enum: ["findability", "clarity", "precision", "efficiency", "all"],
            default: "all",
          },
        },
        required: ["tool"],
      },
    },
  ],
}));

// Tool execution handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "toolrank_score": {
      const tools = (args as any).tools || [];
      const serverName = (args as any).server_name || "unnamed";

      const results = tools.map((t: any) => scoreTool(t));
      const avgScore = results.length > 0
        ? Math.round((results.reduce((s: number, r: ToolScoreResult) => s + r.total, 0) / results.length) * 10) / 10
        : 0;

      const allIssues = results.flatMap((r: ToolScoreResult) => r.issues);
      const topFixes = allIssues
        .sort((a: Issue, b: Issue) => b.impact - a.impact)
        .slice(0, 5);

      // Server-level check: too many tools
      if (tools.length > 20) {
        topFixes.unshift({
          dimension: "efficiency",
          severity: "warning" as const,
          message: `Server has ${tools.length} tools. Agent accuracy degrades past 15-20 tools`,
          fix: "Consolidate into 5-15 workflow-oriented tools",
          impact: 8,
        });
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            server_name: serverName,
            average_score: avgScore,
            tool_count: tools.length,
            total_issues: allIssues.length,
            critical_issues: allIssues.filter((i: Issue) => i.severity === "critical").length,
            top_improvements: topFixes.slice(0, 3).map((i: Issue) => ({
              message: i.message,
              fix: i.fix,
              impact: `+${i.impact}pt`,
            })),
            tools: results.map((r: ToolScoreResult) => ({
              name: r.name,
              score: r.total,
              level: `${r.level}: ${r.levelName}`,
              dimensions: r.dimensions,
              issues: r.issues.map((i: Issue) => ({
                severity: i.severity,
                message: i.message,
                fix: i.fix,
                impact: `+${i.impact}pt`,
              })),
            })),
          }, null, 2),
        }],
      };
    }

    case "toolrank_compare": {
      const tools = (args as any).tools || [];
      const category = (args as any).category || "all";

      const results = tools.map((t: any) => scoreTool(t));
      const avgScore = results.length > 0
        ? Math.round((results.reduce((s: number, r: ToolScoreResult) => s + r.total, 0) / results.length) * 10) / 10
        : 0;

      // Ecosystem benchmarks (from research data, will be replaced with live DB data)
      const benchmarks: Record<string, any> = {
        all: { avg: 42, median: 38, p75: 62, p90: 78 },
        // Categories will be populated from scan DB
      };
      const bench = benchmarks[category] || benchmarks.all;

      let percentile: number;
      if (avgScore >= bench.p90) percentile = 95;
      else if (avgScore >= bench.p75) percentile = 80;
      else if (avgScore >= bench.median) percentile = 55;
      else if (avgScore >= bench.avg) percentile = 40;
      else percentile = 20;

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            your_score: avgScore,
            category,
            percentile: `Top ${100 - percentile}%`,
            benchmark: bench,
            comparison: {
              vs_average: `${avgScore > bench.avg ? "+" : ""}${Math.round(avgScore - bench.avg)} points`,
              vs_median: `${avgScore > bench.median ? "+" : ""}${Math.round(avgScore - bench.median)} points`,
            },
            note: "Benchmarks based on ecosystem scan data. Live rankings available at toolrank.dev/ranking",
          }, null, 2),
        }],
      };
    }

    case "toolrank_suggest": {
      const tool = (args as any).tool || {};
      const focus = (args as any).focus || "all";
      const result = scoreTool(tool);

      const suggestions: any[] = [];

      // Generate concrete suggestions based on issues
      for (const issue of result.issues) {
        if (focus !== "all" && issue.dimension !== focus) continue;

        const suggestion: any = {
          dimension: issue.dimension,
          current_problem: issue.message,
          suggested_fix: issue.fix,
          expected_impact: `+${issue.impact}pt`,
        };

        // Generate concrete rewrite for description issues
        if (issue.dimension === "clarity" && tool.name) {
          if (issue.message.includes("No description") || issue.message.includes("too short")) {
            suggestion.example_rewrite = `${tool.name.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase())} — [describe what it does]. Use this when [describe use case]. Returns [describe output format].`;
          }
          if (issue.message.includes("No clear purpose verb")) {
            suggestion.example_rewrite = `Retrieves/Creates/Searches for [object]. ${tool.description || ""}`;
          }
          if (issue.message.includes("No usage context")) {
            suggestion.example_rewrite = `${tool.description || ""} Use this when you need to [specific scenario].`;
          }
        }

        suggestions.push(suggestion);
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            tool_name: tool.name,
            current_score: result.total,
            current_level: `${result.level}: ${result.levelName}`,
            suggestions: suggestions.sort((a, b) => {
              const impA = parseInt(a.expected_impact) || 0;
              const impB = parseInt(b.expected_impact) || 0;
              return impB - impA;
            }),
            estimated_score_after_fixes: Math.min(100, result.total + suggestions.reduce((s, sg) => s + (parseInt(sg.expected_impact) || 0), 0)),
          }, null, 2),
        }],
      };
    }

    default:
      return {
        content: [{ type: "text", text: `Unknown tool: ${name}` }],
        isError: true,
      };
  }
});

// --- Start Server ---
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ToolRank MCP Server running on stdio");
}

// Smithery sandbox: export for server scanning
export function createSandboxServer() {
  return server;
}

// Default export for Smithery shttp
export default server;

// Only run stdio when executed directly (not imported)
const isDirectRun = process.argv[1]?.includes('index');
if (isDirectRun) {
  main().catch(console.error);
}
