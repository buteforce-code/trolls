import React from 'react'
import { Composition } from 'remotion'
import { BlogPromo } from './BlogPromo'
import { defaultBlogVideoProps } from './video-props'

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="BlogPromo"
        component={BlogPromo}
        durationInFrames={270}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultBlogVideoProps}
      />
      <Composition
        id="BlogLandscape"
        component={BlogPromo}
        durationInFrames={210}
        fps={30}
        width={1200}
        height={630}
        defaultProps={defaultBlogVideoProps}
      />
    </>
  )
}

