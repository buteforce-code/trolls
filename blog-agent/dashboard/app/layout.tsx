import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Buteforce Blog Agent',
  description: 'Autonomous blog content pipeline — research, write, humanise, publish.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <div className="nav-inner">
            <div className="nav-logo">
              {/* Buteforce B-mark */}
              <svg width="26" height="26" viewBox="0 0 145.71 143.63" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M144.5.5l-30.55,30.57h-53.81c-16.06,0-29.07,13.02-29.07,29.07v82.98H.5V53.48C.5,24.22,24.22.5,53.48.5h91.02Z" fill="#0a0a0a"/>
                <path d="M36.33,116.63c-.02,23.54,28.43,35.35,45.09,18.73l26.98-26.92v-.04h.04l26.88-26.9c16.64-16.65,4.85-45.1-18.69-45.1h-53.83c-14.58,0-26.41,11.82-26.42,26.4l-.04,53.83Z" fill="#0a0a0a"/>
              </svg>
              {/* Wordmark */}
              <span style={{ fontWeight: 800, letterSpacing: '-0.5px' }}>ButeForce</span>
              <span className="nav-tag">Blog Agent</span>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  )
}
