import React from 'react';
import {Img, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhotoKey, PHOTOS, PROOF_ORDER} from '../images';

type Props = {
  /** Largeur totale de la bande. */
  width?: number;
  gap?: number;
  /** Image (locale à la scène) où la première photo apparaît. */
  delay?: number;
  /** Écart d'apparition entre deux photos. */
  stagger?: number;
  accent?: string;
  photos?: PhotoKey[];
};

/** Rangée de vraies photos (4:5) qui apparaissent l'une après l'autre. */
export const PhotoStrip: React.FC<Props> = ({width = 880, gap = 16, delay = 0, stagger = 10, accent = '#00F0FF', photos = PROOF_ORDER}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const w = (width - gap * (photos.length - 1)) / photos.length;
  const h = Math.round(w * 1.25);

  return (
    <div style={{display: 'flex', gap, width, justifyContent: 'center'}}>
      {photos.map((k, i) => {
        const p = spring({frame: frame - delay - i * stagger, fps, config: {damping: 12, stiffness: 170, mass: 0.7}});
        const drift = Math.sin((frame + i * 20) / 38) * 5;
        return (
          <div
            key={k}
            style={{
              position: 'relative',
              width: w,
              height: h,
              borderRadius: 22,
              overflow: 'hidden',
              border: `2px solid ${accent}`,
              boxShadow: `0 0 26px ${accent}55`,
              opacity: Math.min(1, p * 1.4),
              transform: `translateY(${(1 - p) * 70 + drift}px) scale(${0.7 + 0.3 * p})`,
            }}
          >
            <Img
              src={PHOTOS[k].src}
              style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: PHOTOS[k].position}}
            />
          </div>
        );
      })}
    </div>
  );
};
