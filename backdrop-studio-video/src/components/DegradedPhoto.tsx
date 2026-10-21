import React from 'react';
import {Img, interpolate, random, useCurrentFrame} from 'remotion';
import {PHOTOS} from '../images';

type Props = {
  width: number;
  height: number;
  /** Image locale où la dégradation commence. */
  start?: number;
  accent?: string;
  /** Identifiant du filtre SVG (unique par instance). */
  filterId?: string;
};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const PHOTO = PHOTOS.grey;
const fill: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'};

/**
 * La vraie photo se dégrade comme un mauvais rendu IA : déformation du visage,
 * peau lissée « cire », reflets, glitchs et ligne de balayage.
 */
export const DegradedPhoto: React.FC<Props> = ({width, height, start = 10, accent = '#FF2A55', filterId = 'degrade-warp'}) => {
  const frame = useCurrentFrame();
  const t = frame - start;

  const melt = interpolate(t, [0, 60], [0, 1], clamp);
  const waxy = interpolate(t, [20, 75], [0, 1], clamp);
  const warp = 36 * melt + Math.sin(frame / 3) * 5 * melt;
  const seed = Math.floor(frame / 3);

  const tick = Math.floor(frame / 5);
  const glitchOn = melt > 0.6 && random(`g${tick}`) > 0.5;
  const slice = (n: number) => {
    const top = random(`s${n}-${tick}`) * 76;
    const h = 4 + random(`h${n}-${tick}`) * 8;
    return {top, bottom: 100 - top - h, dx: (random(`x${n}-${tick}`) - 0.5) * 56};
  };
  const scan = ((frame * 14) % (height + 160)) - 80;

  // Position des reflets dans le cadre (fractions de l'image d'origine).
  const gloss = (fx: number, fy: number, w: number, h: number, o = 0.9) => (
    <div
      style={{
        position: 'absolute',
        left: fx * width - w / 2,
        top: fy * height - h / 2,
        width: w,
        height: h,
        borderRadius: '50%',
        background: 'radial-gradient(ellipse, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0) 70%)',
        opacity: waxy * o,
        mixBlendMode: 'screen',
      }}
    />
  );

  return (
    <div
      style={{
        position: 'relative',
        width,
        height,
        borderRadius: 44,
        overflow: 'hidden',
        background: '#100c20',
        border: '2px solid rgba(255,255,255,0.18)',
        boxShadow: `0 0 ${30 + 40 * melt}px ${accent}${melt > 0.3 ? '55' : '00'}`,
      }}
    >
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="turbulence" baseFrequency="0.008 0.012" numOctaves="2" seed={seed} result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale={warp} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>

      <div style={{position: 'absolute', inset: 0, filter: `url(#${filterId})`, transform: `scale(${1 + 0.03 * melt})`}}>
        <Img src={PHOTO.src} style={fill} />
        <Img src={PHOTO.src} style={{...fill, filter: 'blur(5px) saturate(1.4) brightness(1.12) contrast(0.88)', opacity: waxy * 0.8}} />
        {gloss(0.5, 0.16, width * 0.24, height * 0.12)}
        {gloss(0.57, 0.24, width * 0.15, height * 0.09, 0.8)}
        {gloss(0.45, 0.24, width * 0.14, height * 0.08, 0.7)}
      </div>

      {glitchOn &&
        [0, 1].map((n) => {
          const s = slice(n);
          return (
            <div
              key={n}
              style={{
                position: 'absolute',
                inset: 0,
                clipPath: `inset(${s.top}% 0 ${s.bottom}% 0)`,
                transform: `translateX(${s.dx}px)`,
                filter: n ? 'sepia(1) saturate(6) hue-rotate(150deg)' : 'sepia(1) saturate(6) hue-rotate(-50deg)',
                opacity: 0.8,
              }}
            >
              <Img src={PHOTO.src} style={fill} />
            </div>
          );
        })}

      <div style={{position: 'absolute', left: 0, right: 0, top: scan, height: 6, background: accent, boxShadow: `0 0 30px 6px ${accent}`, opacity: 0.8 * melt}} />
    </div>
  );
};
