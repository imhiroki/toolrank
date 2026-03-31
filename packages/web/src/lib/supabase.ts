import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.SUPABASE_URL || process.env.SUPABASE_URL || '';
const supabaseKey = import.meta.env.SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY || '';

export const supabase = supabaseUrl && supabaseKey
  ? createClient(supabaseUrl, supabaseKey)
  : null;

export interface ServerScore {
  server_name: string;
  display_name: string;
  source: string;
  category: string | null;
  tool_count: number;
  total_score: number;
  findability: number;
  clarity: number;
  precision: number;
  efficiency: number;
  level: number;
  level_name: string;
  scanned_at: string;
}

export async function getLatestScores(limit = 2000): Promise<ServerScore[]> {
  if (!supabase) return [];
  
  try {
    const { data, error } = await supabase
      .from('latest_scores')
      .select('*')
      .order('total_score', { ascending: false })
      .limit(limit);
    
    if (error) {
      console.error('Supabase query error:', error);
      return [];
    }
    
    return data || [];
  } catch (e) {
    console.error('Supabase connection error:', e);
    return [];
  }
}

export async function getScoreDistribution(): Promise<Record<string, number>> {
  if (!supabase) return {};
  
  try {
    const { data, error } = await supabase
      .from('latest_scores')
      .select('total_score');
    
    if (error || !data) return {};
    
    return {
      dominant: data.filter(r => r.total_score >= 85).length,
      preferred: data.filter(r => r.total_score >= 70 && r.total_score < 85).length,
      selectable: data.filter(r => r.total_score >= 50 && r.total_score < 70).length,
      visible: data.filter(r => r.total_score >= 25 && r.total_score < 50).length,
      absent: data.filter(r => r.total_score < 25).length,
      total: data.length,
      average: Math.round(data.reduce((s, r) => s + r.total_score, 0) / data.length * 10) / 10,
    };
  } catch (e) {
    console.error('Distribution query error:', e);
    return {};
  }
}

export async function getLatestSummary() {
  if (!supabase) return null;
  
  try {
    const { data, error } = await supabase
      .from('scan_summaries')
      .select('*')
      .order('scan_date', { ascending: false })
      .limit(1)
      .single();
    
    if (error) return null;
    return data;
  } catch (e) {
    return null;
  }
}

export async function getScanHistory(limit = 12): Promise<Array<{ scan_date: string; scored: number; average_score: number }>> {
  if (!supabase) return [];

  try {
    const { data, error } = await supabase
      .from('scan_summaries')
      .select('scan_date, scored_servers, avg_score')
      .order('scan_date', { ascending: true })
      .limit(limit);

    if (error || !data) return [];
    return data.map(d => ({
      scan_date: d.scan_date,
      scored: d.scored_servers,
      average_score: d.avg_score,
    }));
  } catch (e) {
    return [];
  }
}

export async function getCategories(): Promise<Array<{ category: string; count: number; avg_score: number }>> {
  if (!supabase) return [];

  try {
    const { data, error } = await supabase
      .from('latest_scores')
      .select('category, total_score');

    if (error || !data) return [];

    const cats = new Map<string, { count: number; total: number }>();
    for (const r of data) {
      const c = r.category || 'uncategorized';
      const prev = cats.get(c) || { count: 0, total: 0 };
      cats.set(c, { count: prev.count + 1, total: prev.total + r.total_score });
    }

    return Array.from(cats.entries())
      .map(([category, { count, total }]) => ({
        category,
        count,
        avg_score: Math.round((total / count) * 10) / 10,
      }))
      .filter(c => c.category !== 'uncategorized' && c.count >= 2)
      .sort((a, b) => b.count - a.count);
  } catch (e) {
    return [];
  }
}

export async function getServersByCategory(category: string, limit = 200): Promise<ServerScore[]> {
  if (!supabase) return [];

  try {
    const { data, error } = await supabase
      .from('latest_scores')
      .select('*')
      .eq('category', category)
      .order('total_score', { ascending: false })
      .limit(limit);

    if (error) return [];
    return data || [];
  } catch (e) {
    return [];
  }
}
