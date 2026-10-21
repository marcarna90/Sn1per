import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ShotVariant, StudioShot} from '../components/StudioShot';
import {C, FONT_BODY, FONT_DISPLAY} from '../theme';
import {scene, segment} from '../timeline';

const SHOTS: ShotVariant[] = ['noir', 'velours', 'neon'];
const CHIPS = [
  {text: 'POSES', color: C.cyan},
  {text: 'CADRAGES', color: C.magenta},
  {text: 'DÉCORS', color: C.gold},
  {text: 'LUMIÈRES', color: C.cyan},
];

const CARD = {w: 620, h: 780, top: 285};

export const ProofScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sc = scene('proof');
  const seg = segment('proof');
  const len = seg.frames;

  const head = spring({frame, fps, config: {damping: 13, stiffness: 150}});

  // « Position » flottante du carrousel : saute d'un cran au tiers et aux deux tiers de la phrase.
  const step = (at: number) => spring({frame: frame - at, fps, config: {damping: 16, stiffness: 90, mass: 1}});
  const active = step(Math.round(len * 0.36)) + step(Math.round(len * 0.68));

  const chipsStart = Math.round(len * 0.42);
  const hot = Math.floor(Math.max(0, frame - chipsStart) / 34) % CHIPS.length;
  const label = spring({frame: frame - chipsStart + 6, fps, config: {damping: 14}});

  return (
    <div style={{position: 'absolute', inset: 0}}>
      <div
        style={{
          position: 'absolute',
          top: 112,
          left: 0,
          right: 0,
          textAlign: 'center',
          opacity: head,
          transform: `translateY(${(1 - head) * -50}px)`,
        }}
      >
        <div style={{fontFamily: FONT_BODY, fontWeight: 800, fontSize: 28, letterSpacing: 9, color: C.gold, marginBottom: 2}}>LE RÉSULTAT</div>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 138,
            lineHeight: 0.95,
            backgroundImage: `linear-gradient(90deg, ${C.gold}, #fff2c9 45%, ${C.magenta})`,
            WebkitBackgroundClip: 'text',
            color: 'transparent',
          }}
        >
          RENDU STUDIO LUXE
        </div>
      </div>

      {/* carrousel de maquettes */}
      <div style={{position: 'absolute', left: 0, right: 0, top: CARD.top, height: CARD.h, perspective: 1500}}>
        {SHOTS.map((variant, i) => {
          const pos = i - active;
          const abs = Math.abs(pos);
          const enter = spring({frame: frame - 4 - i * 5, fps, config: {damping: 14, stiffness: 120}});
          const x = pos * 470;
          const scale = (1 - Math.min(abs, 1.6) * 0.2) * (0.7 + 0.3 * enter);
          return (
            <div
              key={variant}
              style={{
                position: 'absolute',
                left: (1080 - CARD.w) / 2,
                top: 0,
                width: CARD.w,
                height: CARD.h,
                opacity: Math.max(0, 1 - abs * 0.42) * enter,
                zIndex: 10 - Math.round(abs * 3),
                transform: `translateX(${x}px) translateY(${(1 - enter) * 120}px) rotateY(${-pos * 24}deg) scale(${scale})`,
                filter: `brightness(${1 - Math.min(abs, 1) * 0.35})`,
                boxShadow: abs < 0.5 ? `0 40px 90px rgba(0,0,0,0.6), 0 0 80px ${C.gold}33` : 'none',
                borderRadius: 40,
              }}
            >
              <StudioShot variant={variant} style={{width: '100%', height: '100%'}} />
            </div>
          );
        })}
      </div>

      {/* bibliothèque modulaire */}
      <div
        style={{
          position: 'absolute',
          top: 1098,
          left: 0,
          right: 0,
          textAlign: 'center',
          fontFamily: FONT_BODY,
          fontWeight: 800,
          fontSize: 25,
          letterSpacing: 7,
          color: C.mute,
          opacity: label,
        }}
      >
        BIBLIOTHÈQUE MODULAIRE
      </div>
      <div style={{position: 'absolute', top: 1146, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 16}}>
        {CHIPS.map((c, i) => {
          const p = spring({frame: frame - chipsStart - i * 5, fps, config: {damping: 10, stiffness: 200, mass: 0.6}});
          const on = i === hot && frame > chipsStart + 22;
          return (
            <div
              key={c.text}
              style={{
                padding: '8px 28px 4px',
                borderRadius: 18,
                fontFamily: FONT_DISPLAY,
                fontSize: 50,
                letterSpacing: 1.5,
                color: on ? '#0b0620' : C.white,
                background: on ? c.color : 'rgba(255,255,255,0.07)',
                border: `3px solid ${c.color}`,
                boxShadow: on ? `0 0 34px ${c.color}` : `0 0 12px ${c.color}44`,
                transform: `scale(${p * (on ? 1.08 : 1)}) translateY(${(1 - p) * 40}px)`,
                opacity: p,
              }}
            >
              {c.text}
            </div>
          );
        })}
      </div>
      <div
        style={{
          position: 'absolute',
          top: 1246,
          left: 60,
          right: 60,
          textAlign: 'center',
          fontFamily: FONT_BODY,
          fontWeight: 500,
          fontSize: 24,
          color: 'rgba(255,255,255,0.5)',
          opacity: label,
        }}
      >
        Visuels illustratifs · les résultats varient selon l&apos;outil IA et la photo de référence
      </div>
    </div>
  );
};
