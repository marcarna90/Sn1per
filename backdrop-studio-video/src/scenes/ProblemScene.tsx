import React from 'react';
import {interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {AlertIcon} from '../components/Icons';
import {Portrait} from '../components/Portrait';
import {C, FONT_BODY, FONT_DISPLAY} from '../theme';

const FACE = {left: 150, top: 250, width: 780, height: 975};
const LABEL_W = 420;

/** Points visés sur le visage, en pixels écran (portrait : viewBox 400x500 placé à 6 % / 8 % du cadre). */
const LABELS = [
  {text: 'VISAGE DÉFORMÉ', at: 34, x: 34, y: 372, side: 'left' as const, target: {x: 478, y: 714}},
  {text: 'PEAU PLASTIQUE', at: 78, x: 626, y: 540, side: 'right' as const, target: {x: 643, y: 800}},
  {text: 'TRAITS PERDUS', at: 120, x: 34, y: 1010, side: 'left' as const, target: {x: 540, y: 826}},
];

const PORTRAIT_PROPS = {
  skin: ['#c98a64', '#7a4a33'] as [string, string],
  hair: '#1b0f0b',
  cloth: '#2a2a35',
};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Le portrait « fond » : fidèle au départ, puis déformé et plastifié.
  const melt = interpolate(frame, [18, 78], [0, 1], clamp);
  const waxy = interpolate(frame, [40, 90], [0, 1], clamp);
  const warp = 24 * melt + Math.sin(frame / 3) * 5 * melt;
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

  return (
    <div style={{position: 'absolute', inset: 0}}>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id="warp" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="turbulence" baseFrequency="0.009 0.014" numOctaves="2" seed={seed} result="noise" />
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
          RENDU IA CLASSIQUE
        </div>
      </div>

      {/* cadre + visage qui se déforme (le filtre ne s'applique qu'au portrait, le cadre reste net) */}
      <div
        style={{
          position: 'absolute',
          ...FACE,
          borderRadius: 48,
          overflow: 'hidden',
          background: 'radial-gradient(ellipse at 50% 30%, #2c2540 0%, #100c20 75%)',
          border: `2px solid ${C.glassBorder}`,
          boxShadow: `0 0 ${30 + 40 * melt}px ${C.red}${melt > 0.3 ? '44' : '00'}`,
        }}
      >
        <div style={{position: 'absolute', inset: 0, filter: 'url(#warp)'}}>
          <div style={{position: 'absolute', inset: '8% 6% 0 6%'}}>
            <Portrait uid="p-ok" {...PORTRAIT_PROPS} distort={melt} />
          </div>
          <div style={{position: 'absolute', inset: '8% 6% 0 6%', opacity: waxy}}>
            <Portrait uid="p-wax" {...PORTRAIT_PROPS} distort={melt} plastic />
          </div>
        </div>

        {glitchOn &&
          [0, 1].map((n) => {
            const s = slice(n);
            return (
              <div
                key={n}
                style={{
                  position: 'absolute',
                  inset: '8% 6% 0 6%',
                  clipPath: `inset(${s.top}% 0 ${s.bottom}% 0)`,
                  transform: `translateX(${s.dx}px)`,
                  filter: n ? 'sepia(1) saturate(6) hue-rotate(150deg)' : 'sepia(1) saturate(6) hue-rotate(-50deg)',
                  opacity: 0.85,
                }}
              >
                <Portrait uid={`p-gl${n}`} {...PORTRAIT_PROPS} distort={1} plastic />
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
          const pulse = 1 + 0.25 * Math.sin(frame / 4 + i);
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
              <circle cx={l.target.x} cy={l.target.y} r={30 * pulse} fill="none" stroke={C.red} strokeWidth={4} />
              <circle cx={l.target.x} cy={l.target.y} r={6} fill={C.red} />
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
              fontSize: 54,
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
