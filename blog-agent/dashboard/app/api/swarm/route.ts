import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

const MAX_RUNS = 40

/**
 * Recent pipeline runs, newest first, with a 24h cost roll-up.
 *
 * Reads through the service key rather than the anon key — the anon read
 * policies on these tables were dropped, so RLS now denies the public path.
 */
export async function GET(request: Request) {
  const limit = Math.min(
    MAX_RUNS,
    Math.max(1, parseInt(new URL(request.url).searchParams.get('limit') || '20', 10) || 20),
  )

  const { data: runs, error } = await supabaseAdmin
    .from('agent_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(limit)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
  const { data: today } = await supabaseAdmin
    .from('agent_runs')
    .select('total_cost_usd,total_input_tokens,total_output_tokens')
    .gte('started_at', since)

  const spend = (today || []).reduce(
    (acc, row) => ({
      costUsd: acc.costUsd + Number(row.total_cost_usd || 0),
      inputTokens: acc.inputTokens + Number(row.total_input_tokens || 0),
      outputTokens: acc.outputTokens + Number(row.total_output_tokens || 0),
      runs: acc.runs + 1,
    }),
    { costUsd: 0, inputTokens: 0, outputTokens: 0, runs: 0 },
  )

  return NextResponse.json({
    runs: runs || [],
    last24h: { ...spend, costUsd: Number(spend.costUsd.toFixed(6)) },
    ceilings: {
      perRunUsd: Number(process.env.MAX_RUN_COST_USD || 3),
      perDayUsd: Number(process.env.MAX_DAILY_COST_USD || 25),
    },
  })
}
