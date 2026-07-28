import { NextResponse } from 'next/server'
// Service key, not anon: RLS on `topics` now has no policies, so an anon read
// returns zero rows rather than an error — a silent empty dashboard.
import { supabaseAdmin as supabase } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

export async function GET() {
  const { data, error } = await supabase
    .from('topics')
    .select('*')
    .order('updated_at', { ascending: false })
    .limit(100)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ topics: data })
}
