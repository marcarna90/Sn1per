import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PROOF_ORDER} from '../images';
import {PhotoCard} from './PhotoCard';

type Props = {
  width?: number;
  height?: number;
  /** Image (locale à la scène) du premier changement de photo. */
  firstStep?: number;
  /** Images entre deux changements de photo. */
  every?: number;
  /** Largeur de la zone visible (les voisines dépassent sur les côtés). */
  stageWidth?: number;
};

/** Carrousel 3D des vraies photos : la photo centrale est mise en avant, les voisines s'effacent. */
export const PhotoCarousel: React.FC<Props> = ({width = 560, height = 700, firstStep = 40, every = 70, stageWidth = 1000}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const step = (at: number) => spring({frame: frame - at, fps, config: {damping: 16, stiffness: 90, mass: 1}});
  const active = PROOF_ORDER.slice(1).reduce((sum, _, k) => sum + step(firstStep + k * every), 0);

  return (
    <div style={{position: 'relative', width: stageWidth, height, perspective: 1500}}>
      {PROOF_ORDER.map((photo, i) => {
        const pos = i - active;
        const abs = Math.abs(pos);
        const enter = spring({frame: frame - 4 - i * 5, fps, config: {damping: 14, stiffness: 120}});
        const scale = (1 - Math.min(abs, 1.6) * 0.2) * (0.7 + 0.3 * enter);
        return (
          <div
            key={photo}
            style={{
              position: 'absolute',
              left: (stageWidth - width) / 2,
              top: 0,
              width,
              height,
              opacity: Math.max(0, 1 - abs * 0.45) * enter,
              zIndex: 10 - Math.round(abs * 3),
              transform: `translateX(${pos * (width * 0.78)}px) translateY(${(1 - enter) * 100}px) rotateY(${-pos * 24}deg) scale(${scale})`,
              filter: `brightness(${1 - Math.min(abs, 1) * 0.35})`,
              boxShadow: abs < 0.5 ? '0 40px 90px rgba(0,0,0,0.6), 0 0 80px rgba(0,240,255,0.18)' : 'none',
              borderRadius: 40,
            }}
          >
            <PhotoCard photo={photo} style={{width: '100%', height: '100%'}} />
          </div>
        );
      })}
    </div>
  );
};
