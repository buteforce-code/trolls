/**
 * All dashboard times render in IST.
 *
 * Pinned rather than left to the browser locale. The operator is in India, the
 * publish cadence is reasoned about in IST, and Google reports in UTC — three
 * clocks in one workflow. A timestamp that silently follows whatever machine
 * opened the page is the one thing guaranteed to cause a mistake, so every
 * displayed time is IST and says so.
 */
const IST = 'Asia/Kolkata'
const LOCALE = 'en-IN'

/** "6 Aug, 2:14 pm" — for dense tables and inline mentions. */
export function fmtIST(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(LOCALE, {
    timeZone: IST, day: 'numeric', month: 'short',
    hour: 'numeric', minute: '2-digit', hour12: true,
  })
}

/** "6 Aug 2026, 2:14 pm IST" — for headers, where the zone must be explicit. */
export function fmtISTLong(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const s = d.toLocaleString(LOCALE, {
    timeZone: IST, day: 'numeric', month: 'short', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true,
  })
  return `${s} IST`
}

/** "6 Aug" — date only, for chart axes. */
export function fmtISTDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(LOCALE, { timeZone: IST, day: 'numeric', month: 'short' })
}

/** "in 6h" / "3d ago". Relative phrasing needs no timezone, but lives here so
 *  every time-rendering decision is in one file. */
export function relative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diff = new Date(iso).getTime() - Date.now()
  if (Number.isNaN(diff)) return '—'
  const abs = Math.abs(diff)
  const hours = Math.round(abs / 3.6e6)
  const unit = hours < 48 ? `${hours}h` : `${Math.round(hours / 24)}d`
  if (abs < 6e4) return 'now'
  return diff > 0 ? `in ${unit}` : `${unit} ago`
}
