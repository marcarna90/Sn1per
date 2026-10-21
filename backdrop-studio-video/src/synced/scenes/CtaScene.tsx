import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ArrowIcon, CheckIcon, CursorIcon} from '../../components/Icons';
import {BRAND, C, FONT_BODY, FONT_DISPLAY} from '../../theme';

const STAR_POINTS = Array.from({length: 48}, (_, i) => {
  const r = i % 2 === 0 ? 168 : 146;
  const a = (i / 48) * Math.PI * 2;
  return `${(Math.cos(a) * r).toFixed(1)},${(Math.sin(a) * r).toFixed(1)}`;
}).join(' ');

const BTN = {w: 900, h: 168, top: 742};

export const CtaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = (delay: number, damping = 11) => spring({frame: frame - delay, fps, config: {damping, stiffness: 170, mass: 0.7}});

  const badge = pop(0, 8);
  const title = pop(10);
  const tag = pop(20);
  const button = pop(30, 9);
  const link = pop(46);
  const price = pop(60);

  // Bouton : rafales de vibration + halo qui clignote.
  const cycle = frame % 46;
  const burst = cycle < 15 ? 1 - cycle / 15 : 0;
  const shakeX = Math.sin(frame * 3.4) * 9 * burst;
  const shakeR = Math.sin(frame * 2.6) * 1.3 * burst;
  const glow = 0.55 + 0.45 * Math.sin(frame / 3.2);
  const press = interpolate(frame % 46, [20, 26, 32], [1, 0.93, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const ring = (offset: number) => {
    const t = ((frame + offset) % 50) / 50;
    return {scale: 1 + t * 0.22, opacity: (1 - t) * 0.65};
  };

  const cursor = pop(78, 14);

  return (
    <div style={{position: 'absolute', inset: 0}}>
      {/* badge promotionnel */}
      <div
        style={{
          position: 'absolute',
          left: 540 - 168,
          top: 118,
          width: 336,
          height: 336,
          transform: `scale(${badge}) rotate(${(1 - badge) * -90 + Math.sin(frame / 14) * 4}deg)`,
          filter: `drop-shadow(0 0 ${22 + glow * 22}px ${C.magenta})`,
        }}
      >
        <svg viewBox="-170 -170 340 340" width={336} height={336} style={{transform: `rotate(${frame * 0.6}deg)`, position: 'absolute', inset: 0}}>
          <defs>
            <linearGradient id="star" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={C.gold} />
              <stop offset="100%" stopColor={C.magenta} />
            </linearGradient>
          </defs>
          <polygon points={STAR_POINTS} fill="url(#star)" />
        </svg>
        <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: FONT_BODY, fontWeight: 900, fontSize: 32, letterSpacing: 6, color: '#2b0a2a', marginBottom: -6}}>PROMO</div>
          <div style={{fontFamily: FONT_DISPLAY, fontSize: 170, lineHeight: 1, color: C.white, textShadow: '0 6px 0 rgba(60,0,60,0.35)'}}>{BRAND.discount}</div>
        </div>
      </div>

      {/* nom du produit */}
      <div
        style={{
          position: 'absolute',
          top: 490,
          left: 0,
          right: 0,
          textAlign: 'center',
          opacity: title,
          transform: `translateY(${(1 - title) * 50}px) scale(${0.9 + 0.1 * title})`,
          fontFamily: FONT_DISPLAY,
          fontSize: 118,
          lineHeight: 1,
          color: C.white,
          whiteSpace: 'nowrap',
          textShadow: `0 0 40px ${C.cyan}66`,
        }}
      >
        BACKDROP STUDIO™ <span style={{color: C.gold}}>PRO</span>
      </div>

      <div
        style={{
          position: 'absolute',
          top: 628,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 14,
          opacity: tag,
          transform: `translateY(${(1 - tag) * 30}px)`,
          fontFamily: FONT_BODY,
          fontWeight: 800,
          fontSize: 34,
          letterSpacing: 3,
          color: C.white,
        }}
      >
        <CheckIcon size={42} color={C.cyan} />
        PACK DISPONIBLE IMMÉDIATEMENT
      </div>

      {/* bouton CTA */}
      <div style={{position: 'absolute', left: (1080 - BTN.w) / 2, top: BTN.top, width: BTN.w, height: BTN.h, opacity: button, transform: `scale(${button})`}}>
        {[0, 25].map((o) => {
          const r = ring(o);
          return (
            <div
              key={o}
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: BTN.h / 2,
                border: `4px solid ${C.cyan}`,
                transform: `scale(${r.scale})`,
                opacity: r.opacity,
              }}
            />
          );
        })}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: BTN.h / 2,
            background: `linear-gradient(100deg, ${C.magenta}, ${C.violet} 55%, ${C.cyan})`,
            boxShadow: `0 0 ${40 + glow * 50}px ${C.magenta}, 0 18px 50px rgba(0,0,0,0.5), inset 0 3px 0 rgba(255,255,255,0.35)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 26,
            transform: `translateX(${shakeX}px) rotate(${shakeR}deg) scale(${press})`,
          }}
        >
          <span style={{fontFamily: FONT_DISPLAY, fontSize: 90, lineHeight: 1, color: C.white, paddingTop: 6, textShadow: '0 4px 0 rgba(0,0,0,0.25)'}}>
            TÉLÉCHARGEZ LE PACK
          </span>
          <div style={{transform: `translateX(${Math.sin(frame / 4) * 8}px)`}}>
            <ArrowIcon size={80} color={C.white} strokeWidth={6} />
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            right: 34,
            top: 104,
            opacity: cursor,
            transform: `translate(${(1 - cursor) * 70}px, ${(1 - cursor) * 90}px) scale(${press < 1 ? 0.88 : 1})`,
            filter: 'drop-shadow(0 8px 14px rgba(0,0,0,0.6))',
          }}
        >
          <CursorIcon size={92} color={C.white} />
        </div>
      </div>

      {/* lien */}
      <div
        style={{
          position: 'absolute',
          top: 958,
          left: 60,
          right: 60,
          height: 124,
          borderRadius: 30,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(255,255,255,0.07)',
          border: `3px solid ${C.cyan}`,
          boxShadow: `0 0 ${20 + glow * 26}px ${C.cyan}77, inset 0 0 30px ${C.cyan}22`,
          opacity: link,
          transform: `translateY(${(1 - link) * 60}px)`,
        }}
      >
        <span style={{fontFamily: FONT_BODY, fontWeight: 800, fontSize: 50, letterSpacing: -0.5, color: C.white, whiteSpace: 'nowrap'}}>{BRAND.url}</span>
      </div>

      {/* prix */}
      <div
        style={{
          position: 'absolute',
          top: 1108,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'baseline',
          gap: 26,
          opacity: price,
          transform: `scale(${0.85 + 0.15 * price})`,
        }}
      >
        <span style={{fontFamily: FONT_BODY, fontWeight: 700, fontSize: 38, color: C.mute, textDecoration: 'line-through'}}>{BRAND.oldPrice}</span>
        <span style={{fontFamily: FONT_DISPLAY, fontSize: 124, lineHeight: 1, color: C.gold, textShadow: `0 0 36px ${C.gold}88`}}>{BRAND.price}</span>
      </div>
      <div
        style={{
          position: 'absolute',
          top: 1236,
          left: 0,
          right: 0,
          textAlign: 'center',
          fontFamily: FONT_BODY,
          fontWeight: 700,
          fontSize: 24,
          letterSpacing: 3,
          color: C.mute,
          opacity: price,
        }}
      >
        PAIEMENT UNIQUE · ACCÈS IMMÉDIAT · 130 DÉCORS
      </div>
    </div>
  );
};
