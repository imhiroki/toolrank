import type { APIRoute } from 'astro';
import { supabase } from '../../../lib/supabase';
import { buildTrustStatus } from '../../../lib/trust-api';

export const prerender = false;

export const GET: APIRoute = async ({ params }) => {
  const serverId = params.id;
  if (!serverId || !supabase) {
    return new Response(JSON.stringify({ error: "Missing server ID or DB not configured" }), {
      status: 400,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  let tier = null;
  let server = null;

  try {
    const { data } = await supabase.from('trust_tiers').select('*').eq('server_id', serverId).single();
    tier = data;
  } catch {}

  try {
    const { data } = await supabase.from('servers').select('*').eq('id', serverId).single();
    server = data;
  } catch {}

  if (!tier && !server) {
    return new Response(JSON.stringify({ error: "Server not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  return new Response(JSON.stringify(buildTrustStatus(tier, server)), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=300",
    },
  });
};
