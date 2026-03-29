/**
 * ToolRank MCP Server - Cloudflare Workers HTTP endpoint
 * 
 * Wraps the ToolRank MCP scoring engine as a Streamable HTTP server
 * for Smithery registration and remote MCP client access.
 * 
 * Deploy: wrangler deploy
 * URL: https://mcp.toolrank.dev/mcp
 */

// Inline scoring engine (simplified Level A for Workers)
function scoreTool(tool) {
  const name = tool.name || '';
  const desc = tool.description || '';
  const schema = tool.inputSchema || tool.input_schema || {};
  const props = schema.properties || {};
  const required = schema.required || [];
  const issues = [];

  // Clarity (max 35)
  let clarity = 0;
  if (!desc.trim()) {
    issues.push({ dim: 'clarity', sev: 'critical', msg: 'No description', fix: 'Add description with purpose, context, return value', impact: 15 });
  } else {
    clarity += 5;
    if (desc.length >= 80 && desc.length <= 250) clarity += 8;
    else if (desc.length >= 50) { clarity += 5; issues.push({ dim: 'clarity', sev: 'warning', msg: `Description ${desc.length} chars (optimal: 80-200)`, fix: 'Expand description', impact: 5 }); }
    else { clarity += 2; issues.push({ dim: 'clarity', sev: 'critical', msg: `Description too short (${desc.length} chars)`, fix: 'Expand to 80-200 chars', impact: 10 }); }
    
    const dl = desc.toLowerCase();
    if (/^(get|set|create|update|delete|search|find|list|fetch|send|retriev|return|provid)/.test(dl)) clarity += 6;
    else { clarity += 3; issues.push({ dim: 'clarity', sev: 'warning', msg: 'No action verb at start', fix: "Start with verb like 'Searches for...', 'Creates...'", impact: 5 }); }
    
    if (/use this|when|useful for|ideal for|designed for/.test(dl)) clarity += 6;
    else { clarity += 2; issues.push({ dim: 'clarity', sev: 'warning', msg: 'No usage context', fix: "Add 'Use this when...'", impact: 6 }); }
    
    if (/returns?|outputs?|produces|yields|result/.test(dl)) clarity += 6;
    else { clarity += 3; issues.push({ dim: 'clarity', sev: 'info', msg: 'No return value described', fix: "Add 'Returns...'", impact: 3 }); }
    
    clarity += 4; // name-desc alignment bonus
  }

  // Precision (max 25)
  let precision = 0;
  if (!schema.type) {
    issues.push({ dim: 'precision', sev: 'critical', msg: 'No input schema', fix: 'Add inputSchema with types', impact: 12 });
  } else {
    precision += 5;
    const pk = Object.keys(props);
    if (pk.length > 0) {
      const noType = pk.filter(k => !props[k].type);
      precision += noType.length === 0 ? 5 : 2;
      if (noType.length > 0) issues.push({ dim: 'precision', sev: 'warning', msg: `Missing types: ${noType.join(', ')}`, fix: 'Add type to each param', impact: 4 });
      
      const noDesc = pk.filter(k => !props[k].description);
      precision += noDesc.length === 0 ? 5 : 2;
      if (noDesc.length > 0) issues.push({ dim: 'precision', sev: 'warning', msg: `Missing param descriptions: ${noDesc.join(', ')}`, fix: 'Add description to each param', impact: 5 });
      
      precision += required.length > 0 ? 5 : 2;
      if (required.length === 0) issues.push({ dim: 'precision', sev: 'info', msg: 'No required fields', fix: 'Add required array', impact: 3 });
      
      precision += 5;
    } else {
      precision += 10;
    }
  }

  // Efficiency (max 15)
  const tokens = JSON.stringify(tool).length / 4;
  let efficiency = tokens > 2000 ? 4 : tokens > 1000 ? 8 : tokens > 500 ? 12 : 15;
  if (tokens > 1000) issues.push({ dim: 'efficiency', sev: 'warning', msg: `~${Math.round(tokens)} tokens`, fix: 'Reduce definition size', impact: 3 });

  // Findability (max 25)
  let findability = name.length >= 4 ? 20 : 8;
  if (name.length < 4) issues.push({ dim: 'findability', sev: 'warning', msg: `Name '${name}' too short`, fix: 'Use descriptive name', impact: 4 });
  if (/^[a-z][a-zA-Z0-9_]*$/.test(name)) findability += 5;
  else { issues.push({ dim: 'findability', sev: 'info', msg: 'Name not snake_case', fix: 'Use snake_case naming', impact: 2 }); }

  const total = Math.round((findability + clarity + precision + efficiency) * 10) / 10;
  let level, levelName;
  if (total >= 85) { level = 4; levelName = 'Dominant'; }
  else if (total >= 70) { level = 3; levelName = 'Preferred'; }
  else if (total >= 50) { level = 2; levelName = 'Selectable'; }
  else if (total >= 25) { level = 1; levelName = 'Visible'; }
  else { level = 0; levelName = 'Absent'; }

  return {
    name, total, level, levelName,
    dimensions: { findability, clarity, precision, efficiency },
    issues: issues.sort((a, b) => b.impact - a.impact),
  };
}

// Tool definitions (what MCP clients see)
const TOOLS = [
  {
    name: "toolrank_score",
    description: "Analyzes MCP tool definitions and returns a ToolRank Score (0-100) measuring agent-readiness. Evaluates four dimensions: Findability (25%), Clarity (35%), Precision (25%), and Efficiency (15%). Use this when you want to check or improve the quality of your MCP tool definitions. Returns per-tool scores, maturity level, specific issues found, and fix suggestions ranked by impact.",
    inputSchema: {
      type: "object",
      properties: {
        tools: {
          type: "array",
          description: "Array of MCP tool definition objects. Each must have 'name' and 'description' fields. 'inputSchema' is optional but improves Precision score.",
          items: {
            type: "object",
            properties: {
              name: { type: "string", description: "Tool name (snake_case recommended)" },
              description: { type: "string", description: "Tool description" },
              inputSchema: { type: "object", description: "JSON Schema for tool input parameters" }
            },
            required: ["name", "description"]
          }
        }
      },
      required: ["tools"]
    }
  },
  {
    name: "toolrank_suggest",
    description: "Generates specific improvement suggestions for MCP tool definitions to increase their ToolRank Score. Use this when you have a low score and want actionable fix recommendations. Returns rewritten description, improved schema, and estimated score improvement for each suggestion.",
    inputSchema: {
      type: "object",
      properties: {
        tool: {
          type: "object",
          description: "Single MCP tool definition to improve",
          properties: {
            name: { type: "string", description: "Tool name" },
            description: { type: "string", description: "Current tool description" },
            inputSchema: { type: "object", description: "Current JSON Schema" }
          },
          required: ["name", "description"]
        }
      },
      required: ["tool"]
    }
  }
];

// Handle MCP protocol messages
function handleMessage(msg) {
  const { method, params, id } = msg;

  switch (method) {
    case "initialize":
      return {
        jsonrpc: "2.0", id,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "toolrank", version: "0.1.1" }
        }
      };

    case "tools/list":
      return { jsonrpc: "2.0", id, result: { tools: TOOLS } };

    case "tools/call": {
      const toolName = params?.name;
      const args = params?.arguments || {};

      if (toolName === "toolrank_score") {
        const tools = args.tools || [];
        const results = tools.map(t => scoreTool(t));
        const avg = results.length > 0
          ? Math.round(results.reduce((s, r) => s + r.total, 0) / results.length * 10) / 10
          : 0;

        return {
          jsonrpc: "2.0", id,
          result: {
            content: [{
              type: "text",
              text: JSON.stringify({ average_score: avg, tools: results }, null, 2)
            }]
          }
        };
      }

      if (toolName === "toolrank_suggest") {
        const tool = args.tool || {};
        const scored = scoreTool(tool);
        const suggestions = scored.issues.slice(0, 5).map(i => ({
          dimension: i.dim,
          issue: i.msg,
          fix: i.fix,
          estimated_impact: `+${i.impact} points`
        }));

        // Generate rewrite
        let newDesc = tool.description || '';
        if (newDesc.length < 50) {
          const parts = (tool.name || '').split(/[_\-]/).filter(p => p.length > 1);
          newDesc = `${(parts[0] || 'Performs').charAt(0).toUpperCase() + (parts[0] || 'performs').slice(1)}s ${parts.slice(1).join(' ') || 'an operation'}. Use this when you need to ${parts.slice(1).join(' ') || 'perform this action'}. Returns the result as structured data.`;
        } else {
          if (!/use this|when|useful for/i.test(newDesc)) newDesc += ` Use this when you need to ${(tool.name || '').replace(/[_\-]/g, ' ')}.`;
          if (!/returns?|outputs?/i.test(newDesc)) newDesc += ' Returns the result as structured data.';
        }

        return {
          jsonrpc: "2.0", id,
          result: {
            content: [{
              type: "text",
              text: JSON.stringify({
                current_score: scored.total,
                suggestions,
                rewritten_description: newDesc
              }, null, 2)
            }]
          }
        };
      }

      return {
        jsonrpc: "2.0", id,
        error: { code: -32601, message: `Unknown tool: ${toolName}` }
      };
    }

    case "notifications/initialized":
    case "ping":
      return method === "ping" ? { jsonrpc: "2.0", id, result: {} } : null;

    default:
      return {
        jsonrpc: "2.0", id,
        error: { code: -32601, message: `Method not found: ${method}` }
      };
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        }
      });
    }

    // Health check
    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/mcp")) {
      return new Response(JSON.stringify({
        name: "toolrank",
        version: "0.1.1",
        description: "ToolRank MCP Server — Score and optimize MCP tool definitions for AI agent discovery.",
        mcp_endpoint: `${url.origin}/mcp`,
        tools: TOOLS.map(t => t.name),
      }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // MCP endpoint
    if (request.method === "POST" && (url.pathname === "/mcp" || url.pathname === "/")) {
      try {
        const body = await request.json();
        
        // Handle batch
        if (Array.isArray(body)) {
          const results = body.map(msg => handleMessage(msg)).filter(r => r !== null);
          return new Response(JSON.stringify(results), {
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
          });
        }

        const result = handleMessage(body);
        if (result === null) {
          return new Response(null, { status: 204 });
        }

        return new Response(JSON.stringify(result), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      } catch (e) {
        return new Response(JSON.stringify({
          jsonrpc: "2.0",
          error: { code: -32700, message: "Parse error" }
        }), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    return new Response("Not found", { status: 404 });
  }
};
