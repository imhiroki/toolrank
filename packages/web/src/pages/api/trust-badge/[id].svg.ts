import type { APIRoute } from 'astro';
import { supabase } from '../../../lib/supabase';
import { buildTrustStatus, generateTrustBadge } from '../../../lib/trust-api';

export const prerender = false;

export const GET: APIRoute = async ({ params }) => {
  const serverId = params.id?.replace(/\.svg$/, "");
  if (!serverId || !supabase) {
    return new Response("Missing server ID", { status: 400 });
  }

  let tier = null;
  let server = null;

  try {
    const { data } = await supabase.from('trust_tiers').select('*').eq('server_id', serverId).single();
    tier = data;
  } catch {}

  try {
    const { data } = await supabase.from('servers').select('id, server_name, display_name').eq('id', serverId).single();
    server = data;
  } catch {}

  const status = buildTrustStatus(tier, server);
  const svg = generateTrustBadge(status);

  return new Response(svg, {
    status: 200,
    headers: {
      "Content-Type": "image/svg+xml",
      "Cache-Control": "public, max-age=3600",
      "Access-Control-Allow-Origin": "*",
    },
  });
};
