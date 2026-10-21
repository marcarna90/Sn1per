import React from 'react';
import {Img, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {AlertIcon} from '../../components/Icons';
import {PHOTOS} from '../../images';
import {C, FONT_BODY, FONT_DISPLAY} from '../../theme';
import {scene, segment} from '../timeline';

const FACE = {left: 150, top: 250, width: 780, height: 975};
const LABEL_W = 440;
const PHOTO = PHOTOS.grey;
/** Échelle photo → cadre (image 1122×1402 affichée en 780×975). */
const S = FACE.width / PHOTO.width;
const at = (px: number, py: number) => ({x: FACE.left + px * S, y: FACE.top + py * S});

/** Points visés sur le visage (coordonnées de l'image d'origine) ; `at` est calculé dans le composant, d'après la voix. */
const LABEL_DEFS = [
  {text: 'VISAGE DÉFORMÉ', x: 34, side: 'left' as const, y: 372, target: at(515, 277)},
  {text: 'PEAU EN PLASTIQUE', x: 1080 - 34 - LABEL_W, side: 'right' as const, y: 290, target: at(565, 225)},
  {text: 'ÉCLAIRAGE FAKE', x: 34, side: 'left' as const, y: 690, target: at(565, 357)},
];

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const photoStyle: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'};

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Les repères d'erreur arrivent quand la voix les nomme : « visage » (phrase 1), « plastique » puis « méconnaissables » (phrase 2).
  const base = scene('problem').from;
  const stop = segment('stop');
  const pain = segment('pain');
  const LABELS = [
    {...LABEL_DEFS[0], at: stop.start - base + 40},
    {...LABEL_DEFS[1], at: pain.start - base + 30},
    {...LABEL_DEFS[2], at: pain.start - base + Math.round(pain.speechFrames * 0.6)},
  ];

  // La vraie photo « fond » : fidèle au départ, puis déformée et plastifiée.
  const melt = interpolate(frame, [18, 78], [0, 1], clamp);
  const waxy = interpolate(frame, [40, 90], [0, 1], clamp);
  const warp = 40 * melt + Math.sin(frame / 3) * 6 * melt;
  const seed = Math.floor(frame / 3);

  const tick = Math.floor(frame / 5);
  const glitchOn = melt > 0.6 && random(`g${tick}`) > 0.5;
  const slice = (n: number) => {
    const top = random(`s${n}-${tick}`) * 76;
    const h = 4 + random(`h${n}-${tick}`) * 8;
    const dx = (random(`x${n}-${tick}`) - 0.5) * 64;
    return {top, bottom: 100 - top - h, dx};
  };

  const header = spring({frame, fps, config: {damping: 14, stiffness: 160}});
  const blink = Math.sin(frame / 5) > 0 ? 1 : 0.25;
  const scan = ((frame * 16) % (FACE.height + 160)) - 80;
  const gloss = (cx: number, cy: number, w: number, h: number, o = 0.9) => {
    const c = at(cx, cy);
    return (
      <div
        style={{
          position: 'absolute',
          left: c.x - FACE.left - w / 2,
          top: c.y - FACE.top - h / 2,
          width: w,
          height: h,
          borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0) 70%)',
          opacity: waxy * o,
          mixBlendMode: 'screen',
        }}
      />
    );
  };

  return (
    <div style={{position: 'absolute', inset: 0}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id="warp" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="turbulence" baseFrequency="0.008 0.012" numOctaves="2" seed={seed} result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale={warp} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>

      {/* bandeau d'alerte */}
      <div
        style={{
          position: 'absolute',
          top: 118,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          opacity: header,
          transform: `translateY(${(1 - header) * -40}px)`,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 18,
            padding: '16px 34px',
            borderRadius: 999,
            border: `2px solid ${C.red}`,
            background: 'rgba(255,59,92,0.12)',
            boxShadow: `0 0 36px ${C.red}55`,
            fontFamily: FONT_BODY,
            fontWeight: 800,
            fontSize: 32,
            letterSpacing: 4,
            color: C.white,
          }}
        >
          <span style={{width: 16, height: 16, borderRadius: '50%', background: C.red, opacity: blink, boxShadow: `0 0 14px ${C.red}`}} />
          STOP AUX PORTRAITS RATÉS
        </div>
      </div>

      {/* cadre + photo qui se dégrade (le filtre ne s'applique qu'à la photo, le cadre reste net) */}
      <div
        style={{
          position: 'absolute',
          ...FACE,
          borderRadius: 48,
          overflow: 'hidden',
          background: '#100c20',
          border: `2px solid ${C.glassBorder}`,
          boxShadow: `0 0 ${30 + 40 * melt}px ${C.red}${melt > 0.3 ? '44' : '00'}`,
        }}
      >
        <div style={{position: 'absolute', inset: 0, filter: 'url(#warp)', transform: `scale(${1 + 0.03 * melt})`}}>
          <Img src={PHOTO.src} style={photoStyle} />
          {/* peau « lissée à outrance » : flou + saturation, fondus sur l'original */}
          <Img
            src={PHOTO.src}
            style={{...photoStyle, filter: 'blur(5px) saturate(1.4) brightness(1.12) contrast(0.88)', opacity: waxy * 0.8}}
          />
          {gloss(565, 225, 190, 120)}
          {gloss(640, 335, 120, 90, 0.8)}
          {gloss(520, 335, 110, 80, 0.7)}
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
                <Img src={PHOTO.src} style={photoStyle} />
              </div>
            );
          })}

        {/* ligne de balayage */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: scan,
            height: 6,
            background: C.red,
            boxShadow: `0 0 30px 6px ${C.red}`,
            opacity: 0.8 * melt,
          }}
        />
      </div>

      {/* repères et lignes de rappel */}
      <svg width={1080} height={1400} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        {LABELS.map((l, i) => {
          const p = interpolate(frame, [l.at + 4, l.at + 18], [0, 1], clamp);
          const ax = l.side === 'left' ? l.x + LABEL_W : l.x + LABEL_W / 2;
          const ay = l.side === 'left' ? l.y + 49 : l.y + 98;
          const pulse = 1 + 0.2 * Math.sin(frame / 4 + i);
          return (
            <g key={i} opacity={p}>
              <line
                x1={ax}
                y1={ay}
                x2={ax + (l.target.x - ax) * p}
                y2={ay + (l.target.y - ay) * p}
                stroke={C.red}
                strokeWidth={4}
                strokeDasharray="10 8"
              />
              <circle cx={l.target.x} cy={l.target.y} r={24 * pulse} fill="none" stroke={C.red} strokeWidth={4} />
              <circle cx={l.target.x} cy={l.target.y} r={5} fill={C.red} />
            </g>
          );
        })}
      </svg>

      {/* étiquettes d'erreur */}
      {LABELS.map((l, i) => {
        const p = spring({frame: frame - l.at, fps, config: {damping: 10, stiffness: 220, mass: 0.6}});
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: l.x,
              top: l.y,
              width: LABEL_W,
              boxSizing: 'border-box',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '14px 24px',
              borderRadius: 18,
              background: 'rgba(20,0,8,0.9)',
              border: `3px solid ${C.red}`,
              boxShadow: `0 0 30px ${C.red}66`,
              fontFamily: FONT_DISPLAY,
              fontSize: 46,
              lineHeight: 1.1,
              letterSpacing: 2,
              color: C.white,
              transform: `scale(${p}) rotate(${(1 - p) * (i % 2 ? 8 : -8)}deg)`,
              opacity: Math.min(1, p),
              transformOrigin: l.side === 'left' ? 'left center' : 'right center',
            }}
          >
            <AlertIcon size={44} color={C.red} />
            {l.text}
          </div>
        );
      })}
    </div>
  );
};
