import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhotoCard} from '../../components/PhotoCard';
import {PROOF_ORDER} from '../../images';
import {C, FONT_BODY, FONT_DISPLAY} from '../../theme';
import {segment} from '../timeline';

const METRICS = [
  {to: 130, label: 'DÉCORS COMPOSITES', color: C.cyan},
  {to: 10, label: 'POSES STUDIO', color: C.magenta},
  {to: 8, label: 'CADRAGES OPTIQUES', color: C.gold},
];

const CARD = {w: 560, h: 700, top: 268};

export const ProofScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const seg = segment('proof');
  const len = seg.frames;

  const head = spring({frame, fps, config: {damping: 13, stiffness: 150}});

  // « Position » flottante du carrousel : avance d'une photo à intervalles réguliers.
  const step = (at: number) => spring({frame: frame - at, fps, config: {damping: 16, stiffness: 90, mass: 1}});
  const active = [0.2, 0.38, 0.56].reduce((sum, t) => sum + step(Math.round(len * t)), 0);

  const metricsStart = Math.round(len * 0.42);
  const boxIn = spring({frame: frame - metricsStart - 24, fps, config: {damping: 14}});
  const noteIn = spring({frame: frame - metricsStart - 34, fps, config: {damping: 14}});

  return (
    <div style={{position: 'absolute', inset: 0}}>
      <div
        style={{
          position: 'absolute',
          top: 100,
          left: 0,
          right: 0,
          textAlign: 'center',
          opacity: head,
          transform: `translateY(${(1 - head) * -50}px)`,
        }}
      >
        <div style={{fontFamily: FONT_BODY, fontWeight: 800, fontSize: 23, letterSpacing: 4, color: C.gold, marginBottom: 4}}>
          OPTIMISÉ POUR CHATGPT IMAGES &amp; GEMINI
        </div>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 128,
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
        {PROOF_ORDER.map((photo, i) => {
          const pos = i - active;
          const abs = Math.abs(pos);
          const enter = spring({frame: frame - 4 - i * 5, fps, config: {damping: 14, stiffness: 120}});
          const x = pos * 430;
          const scale = (1 - Math.min(abs, 1.6) * 0.2) * (0.7 + 0.3 * enter);
          return (
            <div
              key={photo}
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
              <PhotoCard photo={photo} style={{width: '100%', height: '100%'}} />
            </div>
          );
        })}
      </div>

      {/* métriques */}
      <div style={{position: 'absolute', top: 996, left: 60, right: 60, display: 'flex', gap: 16}}>
        {METRICS.map((m, i) => {
          const p = spring({frame: frame - metricsStart - i * 6, fps, config: {damping: 11, stiffness: 190, mass: 0.6}});
          const value = Math.round(interpolate(frame, [metricsStart + i * 6, metricsStart + i * 6 + 30], [0, m.to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
          return (
            <div
              key={m.label}
              style={{
                flex: 1,
                height: 112,
                borderRadius: 22,
                border: `2px solid ${m.color}`,
                background: 'rgba(255,255,255,0.05)',
                boxShadow: `0 0 20px ${m.color}44`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: Math.min(1, p),
                transform: `scale(${p}) translateY(${(1 - p) * 30}px)`,
              }}
            >
              <span style={{fontFamily: FONT_DISPLAY, fontSize: 70, lineHeight: 0.95, color: m.color, textShadow: `0 0 20px ${m.color}88`}}>{value}</span>
              <span style={{fontFamily: FONT_BODY, fontWeight: 700, fontSize: 19, letterSpacing: 1.5, color: C.mute}}>{m.label}</span>
            </div>
          );
        })}
      </div>

      {/* workflow */}
      <div
        style={{
          position: 'absolute',
          top: 1126,
          left: 60,
          right: 60,
          padding: '16px 24px',
          borderRadius: 18,
          border: `2px dashed ${C.cyan}`,
          background: 'rgba(0,240,255,0.08)',
          textAlign: 'center',
          fontFamily: FONT_BODY,
          fontWeight: 700,
          fontSize: 24,
          color: C.white,
          opacity: boxIn,
          transform: `translateY(${(1 - boxIn) * 24}px)`,
        }}
      >
        Workflow Pro en 2 passes : corrigez 1 détail sans toucher au visage
      </div>
      <div
        style={{
          position: 'absolute',
          top: 1218,
          left: 60,
          right: 60,
          textAlign: 'center',
          fontFamily: FONT_BODY,
          fontWeight: 500,
          fontSize: 22,
          color: 'rgba(255,255,255,0.5)',
          opacity: noteIn,
        }}
      >
        Exemples de rendus · les résultats varient selon l&apos;outil IA et la photo de référence
      </div>
    </div>
  );
};
