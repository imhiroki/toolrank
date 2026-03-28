/**
 * ToolRank Dynamic Badge Worker
 * Deploy to Cloudflare Workers.
 * 
 * Usage: https://badge.toolrank.dev/[server-name].svg
 * Example: https://badge.toolrank.dev/brave.svg
 * 
 * Reads score from Supabase and returns a shields.io-style SVG badge.
 */

const SUPABASE_URL = ""; // Set in Worker env vars
const SUPABASE_KEY = ""; // Set in Worker env vars (anon key)

function getColor(score) {
  if (score >= 85) return "#6d28d9"; // Dominant - purple
  if (score >= 70) return "#059669"; // Preferred - green
  if (score >= 50) return "#d97706"; // Selectable - amber
  if (score >= 25) return "#78716c"; // Visible - gray
  return "#dc2626"; // Absent - red
}

function getLabel(score) {
  if (score >= 85) return "Dominant";
  if (score >= 70) return "Preferred";
  if (score >= 50) return "Selectable";
  if (score >= 25) return "Visible";
  return "Absent";
}

function makeBadge(score, serverName) {
  const color = getColor(score);
  const label = `${Math.round(score)} · ${getLabel(score)}`;
  const leftW = 80;
  const rightW = 120;
  const totalW = leftW + rightW;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${totalW}" height="20" role="img" aria-label="ToolRank ${serverName}: ${label}">
  <title>ToolRank ${serverName}: ${label}</title>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="${totalW}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="${leftW}" height="20" fill="#555"/>
    <rect x="${leftW}" width="${rightW}" height="20" fill="${color}"/>
    <rect width="${totalW}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="${leftW / 2}" y="15" fill="#010101" fill-opacity=".3">ToolRank</text>
    <text x="${leftW / 2}" y="14">ToolRank</text>
    <text x="${leftW + rightW / 2}" y="15" fill="#010101" fill-opacity=".3">${label}</text>
    <text x="${leftW + rightW / 2}" y="14">${label}</text>
  </g>
</svg>`;
}

function makeNotFoundBadge(serverName) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="20" role="img">
  <title>ToolRank: not found</title>
  <clipPath id="r"><rect width="180" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)"><rect width="80" height="20" fill="#555"/><rect x="80" width="100" height="20" fill="#999"/><rect width="180" height="20" fill="url(#s)"/></g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">
    <text x="40" y="14">ToolRank</text><text x="130" y="14">not scored</text>
  </g>
</svg>`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\//, "").replace(/\.svg$/, "");
    
    if (!path) {
      return new Response("Usage: /server-name.svg", { status: 400 });
    }

    const supabaseUrl = env.SUPABASE_URL || SUPABASE_URL;
    const supabaseKey = env.SUPABASE_ANON_KEY || SUPABASE_KEY;

    try {
      const resp = await fetch(
        `${supabaseUrl}/rest/v1/latest_scores?server_name=eq.${encodeURIComponent(path)}&select=total_score,server_name&limit=1`,
        {
          headers: {
            apikey: supabaseKey,
            Authorization: `Bearer ${supabaseKey}`,
          },
        }
      );
      const data = await resp.json();

      let svg;
      if (data && data.length > 0) {
        svg = makeBadge(data[0].total_score, path);
      } else {
        svg = makeNotFoundBadge(path);
      }

      return new Response(svg, {
        headers: {
          "Content-Type": "image/svg+xml",
          "Cache-Control": "public, max-age=86400, s-maxage=86400",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch (e) {
      return new Response(makeNotFoundBadge(path), {
        headers: { "Content-Type": "image/svg+xml" },
      });
    }
  },
};
