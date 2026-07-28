import { NextResponse } from 'next/server'
import { supabaseAdmin } from '../../../../lib/supabase'

export const dynamic = 'force-dynamic'

// Matches the uuid the recorder generates. Validated before it reaches a query
// so a malformed id fails fast with a 400 rather than as a database error.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const MAX_EVENTS = 500

/** Every event in one run, in order. `?after=<seq>` returns only newer events. */
export async function GET(request: Request, context: { params: Promise<{ runId: string }> }) {
  const { runId } = await context.params
  if (!UUID_RE.test(runId)) {
    return NextResponse.json({ error: 'Invalid run id' }, { status: 400 })
  }

  const after = Math.max(0, parseInt(new URL(request.url).searchParams.get('after') || '0', 10) || 0)

  const [{ data: run }, { data: events, error }] = await Promise.all([
    supabaseAdmin.from('agent_runs').select('*').eq('id', runId).limit(1).single(),
    supabaseAdmin
      .from('agent_events')
      .select('*')
      .eq('run_id', runId)
      .gt('seq', after)
      .order('seq', { ascending: true })
      .limit(MAX_EVENTS),
  ])

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  if (!run) {
    return NextResponse.json({ error: 'Run not found' }, { status: 404 })
  }

  return NextResponse.json({ run, events: events || [] })
}
