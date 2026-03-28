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

export async function getLatestScores(limit = 100): Promise<ServerScore[]> {
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
