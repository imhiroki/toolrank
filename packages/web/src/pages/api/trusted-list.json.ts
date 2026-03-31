import type { APIRoute } from 'astro';
import { supabase } from '../../lib/supabase';

export const prerender = false;

export const GET: APIRoute = async ({ url }) => {
  if (!supabase) {
    return new Response(JSON.stringify({ error: "DB not configured" }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  const category = url.searchParams.get("category") || "all";
  const minTrust = parseInt(url.searchParams.get("min_trust") || "1");
  const limit = Math.min(parseInt(url.searchParams.get("limit") || "20"), 100);

  try {
    const { data, error } = await supabase
      .from('trust_tiers')
      .select('*')
      .gte('trust_level', minTrust)
      .order('trust_level', { ascending: false })
      .limit(limit);

    if (error) throw error;

    const servers = (data || []).map((t: any, i: number) => ({
      server_id: t.server_id,
      server_name: t.server_name,
      trust_level: t.trust_level,
      spec_score: t.spec_verified_score,
      selection_rate: t.selection_verified_rate,
      rank: i + 1,
      details_url: `https://toolrank.dev/servers/${t.server_id}`,
    }));

    return new Response(JSON.stringify({
      category,
      min_trust_level: minTrust,
      count: servers.length,
      servers,
      _meta: { provider: "ToolRank", api_version: "v1", docs: "https://toolrank.dev/docs/api" },
    }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=600",
      },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: "Query failed" }), {
      status: 500,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }
};
