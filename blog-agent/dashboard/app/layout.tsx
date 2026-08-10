import type { Metadata, Viewport } from 'next'
import { DM_Sans, Sora } from 'next/font/google'
import './globals.css'
import { AppShell } from '../components/shell/app-shell'

/**
 * Fonts are self-hosted through `next/font` rather than a Google Fonts
 * stylesheet link. Two reasons: the link was render-blocking on every route,
 * and it made the app depend on a third-party origin that a tightened CSP would
 * have to keep punching a hole for.
 */
const sora = Sora({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sora',
  display: 'swap',
})

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-dm-sans',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Trolls — Marketing Agent Swarm',
  description: 'Autonomous blog content pipeline — research, write, humanise, publish.',
  icons: { icon: '/brand/buteforce-mark.svg' },
}

export const viewport: Viewport = {
  themeColor: '#F6F5FA',
  colorScheme: 'light',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sora.variable} ${dmSans.variable}`}>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
