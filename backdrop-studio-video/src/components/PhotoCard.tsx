import React from 'react';
import {Img, useCurrentFrame} from 'remotion';
import {PhotoKey, PHOTOS} from '../images';
import {C, FONT_BODY} from '../theme';
import {CheckIcon} from './Icons';

type Props = {
  photo: PhotoKey;
  style?: React.CSSProperties;
};

const CORNERS = [
  {top: 22, left: 22, r: 0},
  {top: 22, right: 22, r: 90},
  {bottom: 22, right: 22, r: 180},
  {bottom: 22, left: 22, r: 270},
] as const;

/** Photo plein cadre avec habillage « viseur » : décor, pose et cadrage, et pastille Identity Lock. */
export const PhotoCard: React.FC<Props> = ({photo, style}) => {
  const frame = useCurrentFrame();
  const p = PHOTOS[photo];
  const zoom = 1.02 + frame * 0.00018; // très léger travelling avant

  return (
    <div style={{position: 'relative', overflow: 'hidden', borderRadius: 40, background: '#0a0714', ...style}}>
      <Img
        src={p.src}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: p.position,
          transform: `scale(${zoom})`,
          transformOrigin: '50% 30%',
        }}
      />

      {/* vignettage + pied de carte lisible */}
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, transparent 55%, rgba(0,0,0,0.45) 100%)'}} />
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 190, background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.72))'}} />

      {CORNERS.map((c, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            width: 44,
            height: 44,
            ...('top' in c ? {top: c.top} : {bottom: c.bottom}),
            ...('left' in c ? {left: c.left} : {right: c.right}),
            borderTop: '4px solid rgba(255,255,255,0.85)',
            borderLeft: '4px solid rgba(255,255,255,0.85)',
            borderTopLeftRadius: 8,
            transform: `rotate(${c.r}deg)`,
          }}
        />
      ))}

      {/* pastille identité */}
      <div
        style={{
          position: 'absolute',
          top: 30,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '8px 18px 8px 12px',
            borderRadius: 999,
            background: 'rgba(5,4,13,0.66)',
            border: `2px solid ${C.cyan}`,
            fontFamily: FONT_BODY,
            fontWeight: 800,
            fontSize: 21,
            letterSpacing: 3,
            color: C.white,
          }}
        >
          <CheckIcon size={26} color={C.cyan} strokeWidth={5} />
          IDENTITY LOCK
        </div>
      </div>

      <div style={{position: 'absolute', left: 38, bottom: 72, fontFamily: FONT_BODY, color: C.white, textShadow: '0 2px 12px rgba(0,0,0,0.9)'}}>
        <div style={{fontWeight: 800, fontSize: 26, letterSpacing: 3}}>{p.decor}</div>
        <div style={{fontWeight: 600, fontSize: 20, letterSpacing: 1.5, marginTop: 6, color: 'rgba(255,255,255,0.82)', whiteSpace: 'nowrap'}}>POSE · {p.pose}</div>
        <div style={{fontWeight: 600, fontSize: 20, letterSpacing: 1.5, marginTop: 2, color: 'rgba(255,255,255,0.82)', whiteSpace: 'nowrap'}}>CADRAGE · {p.cadrage}</div>
      </div>
    </div>
  );
};
