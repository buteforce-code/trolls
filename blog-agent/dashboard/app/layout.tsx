import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Trolls — Marketing Agent Swarm',
  description: 'Autonomous blog content pipeline - research, write, humanise, publish.',
  icons: {
    icon: '/brand/buteforce-mark.svg',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <div className="nav-inner">
            <div className="nav-logo">
              <span className="nav-logo-mark" aria-hidden="true">
                <img src="/brand/buteforce-mark.svg" alt="" />
              </span>
              <img className="nav-logo-wordmark" src="/brand/buteforce-wordmark.png" alt="Buteforce" />
              <span className="nav-tag">Trolls</span>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  )
}
