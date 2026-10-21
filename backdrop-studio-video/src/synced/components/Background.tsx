import React from 'react';
import {AbsoluteFill, interpolate, interpolateColors, random, useCurrentFrame} from 'remotion';
import {C} from '../../theme';
import {SCENES} from '../timeline';

/** Deux couleurs néon par scène ; elles se fondent d'une scène à l'autre. */
const ACCENTS: Record<string, [string, string]> = {
  problem: [C.red, C.magenta],
  reveal: [C.cyan, C.violet],
  proof: [C.gold, C.magenta],
  cta: [C.magenta, C.cyan],
};

const accentAt = (frame: number, index: 0 | 1): string => {
  const mids = SCENES.map((s) => (s.from + s.to) / 2);
  const colors = SCENES.map((s) => ACCENTS[s.id][index]);
  return interpolateColors(frame, mids, colors);
};

const PARTICLES = Array.from({length: 38}, (_, i) => ({
  x: random(`px${i}`) * 1080,
  y: random(`py${i}`) * 1920,
  size: 3 + random(`ps${i}`) * 7,
  speed: 0.25 + random(`pv${i}`) * 0.9,
  phase: random(`pp${i}`) * Math.PI * 2,
}));

export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const a = accentAt(frame, 0);
  const b = accentAt(frame, 1);

  const driftA = Math.sin(frame / 55) * 90;
  const driftB = Math.cos(frame / 70) * 110;
  const pulse = interpolate(Math.sin(frame / 24), [-1, 1], [0.55, 0.85]);

  return (
    <AbsoluteFill style={{background: `linear-gradient(165deg, ${C.bg0} 0%, ${C.bg1} 45%, ${C.bg2} 100%)`}}>
      {/* halos néon */}
      <div
        style={{
          position: 'absolute',
          left: -260 + driftA,
          top: 180 + driftB * 0.5,
          width: 900,
          height: 900,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${a} 0%, transparent 68%)`,
          opacity: 0.34 * pulse,
          filter: 'blur(40px)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: -300 - driftB * 0.4,
          top: 980 + driftA * 0.6,
          width: 1000,
          height: 1000,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${b} 0%, transparent 68%)`,
          opacity: 0.3 * pulse,
          filter: 'blur(50px)',
        }}
      />

      {/* grille discrète en perspective */}
      <svg width={1080} height={1920} style={{position: 'absolute', inset: 0, opacity: 0.16}}>
        {Array.from({length: 14}, (_, i) => {
          const y = 1080 + Math.pow(i / 13, 2.1) * 840 + ((frame * 0.8) % 12);
          return <line key={`h${i}`} x1={0} x2={1080} y1={y} y2={y} stroke={b} strokeWidth={1.4} />;
        })}
        {Array.from({length: 17}, (_, i) => {
          const x = (i - 8) * 150 + 540;
          return <line key={`v${i}`} x1={540 + (x - 540) * 0.18} x2={x * 1.0 + (x - 540) * 1.4} y1={1080} y2={1920} stroke={b} strokeWidth={1.4} />;
        })}
      </svg>

      {/* particules */}
      {PARTICLES.map((p, i) => {
        const y = (p.y - frame * p.speed * 2.2 + 3840) % 1920;
        const x = p.x + Math.sin(frame / 40 + p.phase) * 26;
        const tw = interpolate(Math.sin(frame / 14 + p.phase), [-1, 1], [0.15, 0.7]);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: p.size,
              height: p.size,
              borderRadius: '50%',
              background: i % 2 ? a : b,
              opacity: tw,
              boxShadow: `0 0 14px ${i % 2 ? a : b}`,
            }}
          />
        );
      })}

      {/* vignette */}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.6) 100%)'}} />
    </AbsoluteFill>
  );
};
