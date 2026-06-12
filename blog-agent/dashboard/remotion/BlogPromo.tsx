import React from 'react'
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion'
import { BlogVideoProps } from './video-props'

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

export function BlogPromo({
  title,
  subtitle,
  angle,
  statOne,
  statTwo,
  cta,
}: BlogVideoProps) {
  const frame = useCurrentFrame()
  const { fps, width, height } = useVideoConfig()
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 90 } })
  const isVertical = height > width
  const headlineSize = isVertical ? 78 : 56
  const bodySize = isVertical ? 34 : 24
  const contentWidth = isVertical ? width - 128 : Math.floor(width * 0.62)
  const logoY = isVertical ? 72 : 50
  const titleY = isVertical ? 360 : 170
  const angleY = isVertical ? 900 : 390
  const statY = isVertical ? 1240 : 500
  const accentHeight = interpolate(frame, [0, 42], [0, isVertical ? 520 : 230], {
    extrapolateRight: 'clamp',
  })
  const drift = interpolate(frame, [0, 270], [0, 44], { extrapolateRight: 'clamp' })
  const titleOpacity = interpolate(frame, [8, 32], [0, 1], { extrapolateRight: 'clamp' })
  const footerOpacity = interpolate(frame, [145, 175], [0, 1], { extrapolateRight: 'clamp' })

  return (
    <AbsoluteFill style={{ background: '#f9fafb', fontFamily: 'Inter, Arial, sans-serif' }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(180deg, rgba(255,255,255,0.96), rgba(249,250,251,1) 54%, rgba(255,255,255,1))',
        }}
      />

      <div
        style={{
          position: 'absolute',
          top: -90,
          right: -80,
          width: isVertical ? 410 : 300,
          height: accentHeight,
          background: '#fffc01',
          transform: `skewX(-10deg) translateY(${drift * -0.2}px)`,
          opacity: 0.92,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: isVertical ? 64 : 48,
          top: isVertical ? 210 : 124,
          width: 6,
          height: clamp(accentHeight * 0.72, 0, isVertical ? 420 : 180),
          background: '#fffc01',
        }}
      />

      <Img
        src={staticFile('brand/buteforce-wordmark.png')}
        style={{
          position: 'absolute',
          top: logoY,
          left: isVertical ? 64 : 48,
          width: isVertical ? 230 : 154,
          height: 'auto',
          opacity: interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' }),
        }}
      />

      <div
        style={{
          position: 'absolute',
          top: titleY,
          left: isVertical ? 64 : 48,
          width: contentWidth,
          opacity: titleOpacity,
          transform: `translateY(${(1 - enter) * 38}px)`,
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            padding: isVertical ? '9px 16px' : '7px 12px',
            marginBottom: isVertical ? 34 : 20,
            border: '1px solid #e5e7eb',
            background: '#ffffff',
            color: '#0a0a0a',
            fontSize: isVertical ? 20 : 13,
            fontWeight: 700,
            letterSpacing: 0.4,
            textTransform: 'uppercase',
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: 10, background: '#fffc01' }} />
          Precision AI Systems
        </div>

        <div
          style={{
            color: '#0a0a0a',
            fontWeight: 850,
            fontSize: headlineSize,
            lineHeight: 1.02,
            letterSpacing: -1.2,
          }}
        >
          {title}
        </div>
        <div
          style={{
            marginTop: isVertical ? 28 : 18,
            color: '#525866',
            fontSize: bodySize,
            lineHeight: 1.35,
            maxWidth: isVertical ? contentWidth : 700,
          }}
        >
          {subtitle}
        </div>
      </div>

      <Sequence from={70}>
        <div
          style={{
            position: 'absolute',
            top: angleY,
            left: isVertical ? 64 : Math.floor(width * 0.52),
            width: isVertical ? contentWidth : Math.floor(width * 0.38),
            padding: isVertical ? '34px 36px' : '24px 26px',
            background: '#0a0a0a',
            color: '#ffffff',
            borderRadius: 8,
            boxShadow: '0 18px 55px rgba(10,10,10,0.16)',
            opacity: interpolate(frame, [70, 96], [0, 1], { extrapolateRight: 'clamp' }),
            transform: `translateY(${interpolate(frame, [70, 96], [28, 0], {
              extrapolateRight: 'clamp',
            })}px)`,
          }}
        >
          <div style={{ color: '#fffc01', fontWeight: 800, fontSize: isVertical ? 20 : 13, marginBottom: 14 }}>
            BUTEFORCE ANGLE
          </div>
          <div style={{ fontSize: isVertical ? 31 : 20, lineHeight: 1.35 }}>{angle}</div>
        </div>
      </Sequence>

      <Sequence from={118}>
        <div
          style={{
            position: 'absolute',
            top: statY,
            left: isVertical ? 64 : 48,
            display: 'flex',
            gap: isVertical ? 22 : 14,
            opacity: interpolate(frame, [118, 144], [0, 1], { extrapolateRight: 'clamp' }),
          }}
        >
          {[statOne, statTwo].map((stat, index) => (
            <div
              key={stat}
              style={{
                minWidth: isVertical ? 212 : 128,
                padding: isVertical ? '24px 26px' : '16px 18px',
                background: '#ffffff',
                border: '1px solid #e5e7eb',
                borderTop: '5px solid #fffc01',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              }}
            >
              <div style={{ color: '#0a0a0a', fontWeight: 850, fontSize: isVertical ? 44 : 28 }}>
                {stat}
              </div>
              <div style={{ color: '#7a828e', fontSize: isVertical ? 17 : 11, marginTop: 4 }}>
                {index === 0 ? 'brief to publish' : 'content output'}
              </div>
            </div>
          ))}
        </div>
      </Sequence>

      <div
        style={{
          position: 'absolute',
          left: isVertical ? 64 : 48,
          right: isVertical ? 64 : 48,
          bottom: isVertical ? 72 : 44,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          opacity: footerOpacity,
          color: '#0a0a0a',
          fontSize: isVertical ? 23 : 15,
          fontWeight: 700,
        }}
      >
        <span>No consultants. No pilot projects. Working systems.</span>
        <span>{cta}</span>
      </div>
    </AbsoluteFill>
  )
}

