/**
 * ToolRank Trust Status API
 * =========================
 * Counters: "Distribution integration" attack vector.
 * Strategy: Make ToolRank the trust data source that registries consume.
 *
 * Endpoints:
 *   GET  /api/trust-status/:serverId  → Full trust profile
 *   GET  /api/trusted-list?category=X → Trusted servers for a category
 *   GET  /api/trust-badge/:serverId   → SVG badge with trust tier
 *   POST /api/verify                  → Verify a server (with API key)
 *
 * This is designed to be consumed by:
 *   - MCP registries (Official, MCP.so, Smithery)
 *   - Agent frameworks (LangChain, CrewAI)
 *   - CI/CD pipelines
 *   - Client applications selecting trusted servers
 */

// ── Types ──────────────────────────────────────────────────
interface TrustStatus {
  server_id: string;
  server_name: string;
  trust_level: number;           // 0-3
  trust_label: string;           // "Untrusted" | "Spec Verified" | "Selection Verified" | "Fully Verified"

  spec: {
    verified: boolean;
    score: number | null;
    verified_at: string | null;
    expires_at: string | null;
  };

  selection: {
    verified: boolean;
    win_rate: number | null;
    total_rounds: number | null;
    verified_at: string | null;
    expires_at: string | null;
  };

  runtime: {
    verified: boolean;
    data: Record<string, unknown>;
    verified_at: string | null;
    expires_at: string | null;
  };

  // For distribution integration
  recommended: boolean;           // trust_level >= 2
  deployment_safe: boolean;       // trust_level >= 1 && no active warnings

  audit_url: string;              // Link to full audit log
  details_url: string;            // Link to ToolRank server page
  badge_url: string;              // Embeddable badge URL
  updated_at: string;
}

interface TrustedListEntry {
  server_id: string;
  server_name: string;
  category: string;
  trust_level: number;
  spec_score: number | null;
  selection_rate: number | null;
  rank: number;
  details_url: string;
}

// ── Trust Level Labels ─────────────────────────────────────
const TRUST_LABELS: Record<number, string> = {
  0: "Unverified",
  1: "Spec Verified",
  2: "Selection Verified",
  3: "Fully Verified",
};

// ── Badge Colors ───────────────────────────────────────────
const BADGE_COLORS: Record<number, string> = {
  0: "#6b7280", // gray
  1: "#3b82f6", // blue
  2: "#8b5cf6", // purple
  3: "#10b981", // green
};

// ── Helper: Create Trust Status Response ───────────────────
function buildTrustStatus(tier: any, server: any): TrustStatus {
  const trustLevel = tier?.trust_level ?? 0;
  const serverId = tier?.server_id ?? server?.id ?? "";
  const serverName = tier?.server_name ?? server?.display_name ?? server?.server_name ?? "";

  return {
    server_id: serverId,
    server_name: serverName,
    trust_level: trustLevel,
    trust_label: TRUST_LABELS[trustLevel] ?? "Unverified",

    spec: {
      verified: tier?.spec_verified === "earned",
      score: tier?.spec_verified_score ?? server?.score ?? null,
      verified_at: tier?.spec_verified_at ?? null,
      expires_at: tier?.spec_expires_at ?? null,
    },

    selection: {
      verified: tier?.selection_verified === "earned",
      win_rate: tier?.selection_verified_rate ?? null,
      total_rounds: null,
      verified_at: tier?.selection_verified_at ?? null,
      expires_at: tier?.selection_expires_at ?? null,
    },

    runtime: {
      verified: tier?.runtime_verified === "earned",
      data: tier?.runtime_verified_data ?? {},
      verified_at: tier?.runtime_verified_at ?? null,
      expires_at: tier?.runtime_expires_at ?? null,
    },

    recommended: trustLevel >= 2,
    deployment_safe: trustLevel >= 1,

    audit_url: `https://toolrank.dev/trust/${serverId}/audit`,
    details_url: `https://toolrank.dev/servers/${serverId}`,
    badge_url: `https://mcp.toolrank.dev/api/trust-badge/${serverId}`,
    updated_at: tier?.updated_at ?? new Date().toISOString(),
  };
}

// ── Helper: Generate SVG Badge ─────────────────────────────
function generateTrustBadge(status: TrustStatus): string {
  const color = BADGE_COLORS[status.trust_level] ?? BADGE_COLORS[0];
  const label = status.trust_label;
  const score = status.spec.score ? `${Math.round(status.spec.score)}` : "—";
  const winRate = status.selection.win_rate ? ` | Win ${Math.round(status.selection.win_rate)}%` : "";

  const labelWidth = 80;
  const valueText = `${score}${winRate}`;
  const valueWidth = Math.max(90, valueText.length * 7.5 + 16);
  const totalWidth = labelWidth + valueWidth;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="24" role="img" aria-label="ToolRank Trust: ${label}">
  <title>ToolRank Trust: ${label} — Score ${score}${winRate}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="${totalWidth}" height="24" rx="4" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="${labelWidth}" height="24" fill="#1a1a2e"/>
    <rect x="${labelWidth}" width="${valueWidth}" height="24" fill="${color}"/>
    <rect width="${totalWidth}" height="24" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="${labelWidth / 2}" y="16.5" fill="#fff">ToolRank</text>
    <text x="${labelWidth + valueWidth / 2}" y="16.5" font-weight="bold">${label} ${score}${winRate}</text>
  </g>
</svg>`;
}

// ── Export for Cloudflare Worker / Astro API ────────────────
export {
  buildTrustStatus,
  generateTrustBadge,
  TRUST_LABELS,
  BADGE_COLORS,
};

export type { TrustStatus, TrustedListEntry };

// ── Astro API Route Handlers ────────────────────────────────
// These are designed as Astro API route functions.
// Copy to src/pages/api/ as needed.

/**
 * GET /api/trust-status/[id]
 * Returns full trust profile for a server.
 * Used by: registries, agent frameworks, CI/CD tools.
 */
export async function handleTrustStatus(serverId: string, supabaseUrl: string, supabaseKey: string) {
  const headers = {
    "apikey": supabaseKey,
    "Authorization": `Bearer ${supabaseKey}`,
  };

  // Fetch trust tier
  const tierRes = await fetch(
    `${supabaseUrl}/rest/v1/trust_tiers?server_id=eq.${serverId}&limit=1`,
    { headers }
  );
  const tiers = await tierRes.json();
  const tier = tiers?.[0] ?? null;

  // Fetch server info
  const serverRes = await fetch(
    `${supabaseUrl}/rest/v1/servers?id=eq.${serverId}&limit=1`,
    { headers }
  );
  const servers = await serverRes.json();
  const server = servers?.[0] ?? null;

  if (!tier && !server) {
    return { status: 404, body: { error: "Server not found" } };
  }

  return {
    status: 200,
    body: buildTrustStatus(tier, server),
  };
}

/**
 * GET /api/trusted-list?category=X&min_trust=N
 * Returns trusted servers for a category.
 * Used by: registries to show "ToolRank Verified" placements.
 */
export async function handleTrustedList(
  category: string,
  minTrust: number,
  supabaseUrl: string,
  supabaseKey: string,
  limit: number = 20
) {
  const headers = {
    "apikey": supabaseKey,
    "Authorization": `Bearer ${supabaseKey}`,
  };

  const url = new URL(`${supabaseUrl}/rest/v1/trust_tiers`);
  url.searchParams.set("trust_level", `gte.${minTrust}`);
  url.searchParams.set("order", "trust_level.desc");
  url.searchParams.set("limit", String(limit));

  const res = await fetch(url.toString(), { headers });
  const tiers = await res.json();

  return {
    status: 200,
    body: {
      category,
      min_trust_level: minTrust,
      count: tiers.length,
      servers: tiers.map((t: any, i: number) => ({
        server_id: t.server_id,
        server_name: t.server_name,
        trust_level: t.trust_level,
        spec_score: t.spec_verified_score,
        selection_rate: t.selection_verified_rate,
        rank: i + 1,
        details_url: `https://toolrank.dev/servers/${t.server_id}`,
      })),
      _meta: {
        provider: "ToolRank",
        api_version: "v1",
        docs: "https://toolrank.dev/docs/api",
      }
    }
  };
}
