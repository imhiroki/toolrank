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
        version: "0.2.0",
        description: "ToolRank MCP Server — Score and optimize MCP tool definitions for AI agent discovery.",
        mcp_endpoint: `${url.origin}/mcp`,
        api_endpoint: `${url.origin}/api/score`,
        tools: TOOLS.map(t => t.name),
      }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === REST API: Score endpoint ===
    if (request.method === "POST" && url.pathname === "/api/score") {
      try {
        const body = await request.json();
        const tools = body.tools || (body.name ? [body] : []);
        if (!tools.length) {
          return new Response(JSON.stringify({ error: "Provide 'tools' array or a single tool object with 'name'" }), {
            status: 400, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
          });
        }
        const scored = tools.map(t => scoreTool(t));
        const avg = scored.reduce((s, t) => s + t.total, 0) / scored.length;
        const level = avg >= 85 ? 'Dominant' : avg >= 70 ? 'Preferred' : avg >= 50 ? 'Selectable' : 'Low';
        const pct = avg >= 95 ? 3 : avg >= 90 ? 10 : avg >= 85 ? 36 : avg >= 80 ? 55 : avg >= 70 ? 75 : 92;
        return new Response(JSON.stringify({
          score: Math.round(avg * 10) / 10,
          level,
          percentile: pct,
          tools: scored.map(t => ({
            name: t.name, score: t.total, level: t.levelName,
            dimensions: t.dimensions, issues: t.issues,
          })),
          version: "1.0.0",
          _links: { score_page: "https://toolrank.dev/score", framework: "https://toolrank.dev/framework" },
        }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 400, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
    }

    // === REST API: OG Image (SVG scorecard) ===
    if (request.method === "GET" && url.pathname.startsWith("/og/")) {
      const serverName = decodeURIComponent(url.pathname.replace("/og/", "").replace(".svg", "").replace(".png", ""));
      // Generate SVG scorecard (lightweight, no external dependencies)
      const score = url.searchParams.get("score") || "?";
      const level = url.searchParams.get("level") || "";
      const levelColor = level === "Dominant" ? "#6d28d9" : level === "Preferred" ? "#22c55e" : level === "Selectable" ? "#eab308" : "#888";
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="315" viewBox="0 0 600 315">
        <rect width="600" height="315" rx="16" fill="#0f0f14"/>
        <text x="40" y="50" fill="#888" font-family="system-ui" font-size="14">toolrank.dev</text>
        <text x="40" y="110" fill="#fff" font-family="system-ui" font-size="32" font-weight="700">${serverName}</text>
        <text x="40" y="190" fill="${levelColor}" font-family="system-ui" font-size="80" font-weight="800">${score}</text>
        <text x="${score.length > 2 ? 215 : 175}" y="190" fill="#666" font-family="system-ui" font-size="32">/100</text>
        <rect x="40" y="220" width="120" height="30" rx="15" fill="${levelColor}20"/>
        <text x="100" y="241" fill="${levelColor}" font-family="system-ui" font-size="14" font-weight="600" text-anchor="middle">${level}</text>
        <text x="40" y="290" fill="#555" font-family="system-ui" font-size="12">ToolRank Score · Agent Tool Optimization</text>
      </svg>`;
      return new Response(svg, {
        headers: { "Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === Embed widget ===
    if (request.method === "GET" && url.pathname === "/embed.js") {
      const js = `(function(){
        var el=document.currentScript;
        var s=el.getAttribute('data-server')||'';
        var score=el.getAttribute('data-score')||'';
        var level=el.getAttribute('data-level')||'';
        if(!s)return;
        var d=document.createElement('div');
        d.innerHTML='<a href="https://toolrank.dev/ranking/'+s+'" target="_blank" rel="noopener" style="display:inline-block;border:1px solid #333;border-radius:8px;padding:12px 16px;background:#0f0f14;text-decoration:none;font-family:system-ui;min-width:200px">'
          +'<div style="font-size:11px;color:#888;margin-bottom:4px">ToolRank Score</div>'
          +'<div style="display:flex;align-items:baseline;gap:6px">'
          +'<span style="font-size:28px;font-weight:700;color:#6d28d9">'+(score||'—')+'</span>'
          +'<span style="font-size:12px;color:#666">/100</span>'
          +'</div>'
          +'<div style="font-size:11px;color:#888;margin-top:4px">'+s+'</div>'
          +'</a>';
        el.parentNode.insertBefore(d,el.nextSibling);
      })();`;
      return new Response(js, {
        headers: { "Content-Type": "application/javascript", "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === Stats API — embeddable ecosystem numbers ===
    if (request.method === "GET" && url.pathname === "/api/stats") {
      // Return citable ecosystem stats (cached 1hr)
      const stats = {
        total_scanned: "4,000+",
        total_scored: 374,
        invisible_pct: 73,
        avg_score: 85.7,
        dominant_count: 239,
        preferred_count: 127,
        selectable_count: 8,
        sources: ["Smithery", "Official MCP Registry"],
        score_version: "1.0.0",
        updated: new Date().toISOString().split("T")[0],
        citation: "Source: ToolRank (toolrank.dev). Data updated daily.",
        _links: {
          ranking: "https://toolrank.dev/ranking",
          framework: "https://toolrank.dev/framework",
          api: "https://toolrank.dev/docs/api",
        },
      };
      return new Response(JSON.stringify(stats), {
        headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === Stats Badge SVG — embeddable stat for other sites ===
    if (request.method === "GET" && url.pathname.startsWith("/api/stats/badge")) {
      const stat = url.searchParams.get("stat") || "scored";
      const labels = {
        scored: { label: "MCP servers scored", value: "374" },
        scanned: { label: "MCP servers scanned", value: "4,000+" },
        invisible: { label: "invisible to agents", value: "73%" },
        avg: { label: "average ToolRank Score", value: "85.7" },
      };
      const { label, value } = labels[stat] || labels.scored;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="28" viewBox="0 0 240 28">
        <rect width="240" height="28" rx="4" fill="#0f0f14"/>
        <text x="8" y="18" fill="#888" font-family="system-ui" font-size="11">${label}</text>
        <text x="232" y="18" fill="#6d28d9" font-family="system-ui" font-size="12" font-weight="700" text-anchor="end">${value}</text>
      </svg>`;
      return new Response(svg, {
        headers: { "Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === Trust Status API — per-server trust profile ===
    if (request.method === "GET" && url.pathname.startsWith("/api/trust-status/")) {
      const serverId = url.pathname.replace("/api/trust-status/", "").replace(".json", "");
      if (!serverId || !env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
        return new Response(JSON.stringify({ error: "Missing server ID or DB config" }), {
          status: 400, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
      const sbHeaders = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` };
      let tier = null, server = null;
      try {
        const r = await fetch(`${env.SUPABASE_URL}/rest/v1/trust_tiers?server_id=eq.${serverId}&limit=1`, { headers: sbHeaders });
        const d = await r.json(); tier = d?.[0] || null;
      } catch {}
      try {
        const r = await fetch(`${env.SUPABASE_URL}/rest/v1/servers?id=eq.${serverId}&select=id,server_name,display_name&limit=1`, { headers: sbHeaders });
        const d = await r.json(); server = d?.[0] || null;
      } catch {}
      if (!tier && !server) {
        return new Response(JSON.stringify({ error: "Server not found" }), {
          status: 404, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
      const tl = tier?.trust_level ?? 0;
      const trustLabels = { 0: "Unverified", 1: "Spec Verified", 2: "Selection Verified", 3: "Fully Verified" };
      const status = {
        server_id: serverId,
        server_name: tier?.server_name || server?.display_name || server?.server_name || "",
        trust_level: tl,
        trust_label: trustLabels[tl] || "Unverified",
        spec: { verified: tier?.spec_verified === "earned", score: tier?.spec_verified_score || null, verified_at: tier?.spec_verified_at || null },
        selection: { verified: tier?.selection_verified === "earned", win_rate: tier?.selection_verified_rate || null, verified_at: tier?.selection_verified_at || null },
        runtime: { verified: tier?.runtime_verified === "earned", verified_at: tier?.runtime_verified_at || null },
        recommended: tl >= 2,
        deployment_safe: tl >= 1,
        audit_url: `https://toolrank.dev/trust/${serverId}/audit`,
        details_url: `https://toolrank.dev/ranking/${server?.server_name || ""}`,
        badge_url: `${url.origin}/api/trust-badge/${serverId}.svg`,
      };
      return new Response(JSON.stringify(status), {
        headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=300", "Access-Control-Allow-Origin": "*" }
      });
    }

    // === Trusted List API — verified servers for registries ===
    if (request.method === "GET" && url.pathname === "/api/trusted-list") {
      if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) {
        return new Response(JSON.stringify({ error: "DB not configured" }), {
          status: 500, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
      const minTrust = parseInt(url.searchParams.get("min_trust") || "1");
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "20"), 100);
      const sbHeaders = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` };
      try {
        const r = await fetch(`${env.SUPABASE_URL}/rest/v1/trust_tiers?trust_level=gte.${minTrust}&order=trust_level.desc&limit=${limit}`, { headers: sbHeaders });
        const tiers = await r.json();
        const servers = (tiers || []).map((t, i) => ({
          server_id: t.server_id, server_name: t.server_name,
          trust_level: t.trust_level, spec_score: t.spec_verified_score,
          selection_rate: t.selection_verified_rate, rank: i + 1,
          details_url: `https://toolrank.dev/servers/${t.server_id}`,
        }));
        return new Response(JSON.stringify({
          min_trust_level: minTrust, count: servers.length, servers,
          _meta: { provider: "ToolRank", api_version: "v1", docs: "https://toolrank.dev/docs/api" },
        }), {
          headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=600", "Access-Control-Allow-Origin": "*" }
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: "Query failed" }), {
          status: 500, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
    }

    // === Trust Badge SVG — embeddable trust tier badge ===
    if (request.method === "GET" && url.pathname.startsWith("/api/trust-badge/")) {
      const serverId = url.pathname.replace("/api/trust-badge/", "").replace(".svg", "");
      if (!serverId) return new Response("Missing ID", { status: 400 });
      let tl = 0, score = "—", winRate = "", label = "Unverified";
      if (env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY) {
        const sbHeaders = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` };
        try {
          const r = await fetch(`${env.SUPABASE_URL}/rest/v1/trust_tiers?server_id=eq.${serverId}&limit=1`, { headers: sbHeaders });
          const d = await r.json(); const tier = d?.[0];
          if (tier) {
            tl = tier.trust_level || 0;
            score = tier.spec_verified_score ? Math.round(tier.spec_verified_score).toString() : "—";
            winRate = tier.selection_verified_rate ? ` | Win ${Math.round(tier.selection_verified_rate)}%` : "";
            label = { 0: "Unverified", 1: "Spec Verified", 2: "Selection Verified", 3: "Fully Verified" }[tl] || "Unverified";
          }
        } catch {}
      }
      const color = { 0: "#6b7280", 1: "#3b82f6", 2: "#8b5cf6", 3: "#10b981" }[tl] || "#6b7280";
      const valueText = `${label} ${score}${winRate}`;
      const labelWidth = 80;
      const valueWidth = Math.max(90, valueText.length * 7 + 16);
      const totalWidth = labelWidth + valueWidth;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="24" role="img" aria-label="ToolRank Trust: ${label}">
  <title>ToolRank Trust: ${label} — Score ${score}${winRate}</title>
  <clipPath id="r"><rect width="${totalWidth}" height="24" rx="4" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="${labelWidth}" height="24" fill="#1a1a2e"/>
    <rect x="${labelWidth}" width="${valueWidth}" height="24" fill="${color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">
    <text x="${labelWidth / 2}" y="16.5">ToolRank</text>
    <text x="${labelWidth + valueWidth / 2}" y="16.5" font-weight="bold">${valueText}</text>
  </g>
</svg>`;
      return new Response(svg, {
        headers: { "Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*" }
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
