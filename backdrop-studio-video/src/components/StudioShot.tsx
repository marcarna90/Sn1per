import React from 'react';
import {useCurrentFrame} from 'remotion';
import {FONT_BODY} from '../theme';
import {HairStyle, Portrait} from './Portrait';

export type ShotVariant = 'noir' | 'velours' | 'neon';

type Look = {
  backdrop: string;
  floor: string;
  key: string;
  rim: string;
  skin: [string, string];
  hair: string;
  hairStyle: HairStyle;
  cloth: string;
  clothAccent: string;
  label: string;
  exif: string;
};

const LOOKS: Record<ShotVariant, Look> = {
  noir: {
    backdrop: 'radial-gradient(ellipse at 50% 30%, #3a3327 0%, #14110c 62%, #07060a 100%)',
    floor: 'linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.65) 100%)',
    key: 'rgba(255, 214, 140, 0.55)',
    rim: '#ffd27a',
    skin: ['#8a5a3f', '#4d2f21'],
    hair: '#120c09',
    hairStyle: 'afro',
    cloth: '#15151b',
    clothAccent: 'rgba(255, 200, 90, 0.7)',
    label: 'NOIR & OR',
    exif: '85mm · f/1.8 · ISO 100',
  },
  velours: {
    backdrop:
      'repeating-linear-gradient(90deg, rgba(0,0,0,0.28) 0px, rgba(0,0,0,0) 34px, rgba(255,120,150,0.12) 62px, rgba(0,0,0,0.28) 96px), radial-gradient(ellipse at 50% 25%, #8a1f3d 0%, #44091e 65%, #1a0309 100%)',
    floor: 'linear-gradient(180deg, transparent 0%, rgba(20,0,6,0.7) 100%)',
    key: 'rgba(255, 190, 200, 0.5)',
    rim: '#ffb3c4',
    skin: ['#c98a64', '#7a4a33'],
    hair: '#1b0f0b',
    hairStyle: 'long',
    cloth: '#efe3d2',
    clothAccent: 'rgba(120, 60, 40, 0.5)',
    label: 'VELOURS BORDEAUX',
    exif: '70mm · f/2.0 · ISO 160',
  },
  neon: {
    backdrop: 'radial-gradient(ellipse at 50% 28%, #1d3a7a 0%, #0b1236 60%, #04061a 100%)',
    floor: 'linear-gradient(180deg, transparent 0%, rgba(0,0,12,0.7) 100%)',
    key: 'rgba(120, 230, 255, 0.5)',
    rim: '#5ff0ff',
    skin: ['#6b4331', '#3a2218'],
    hair: '#0a0706',
    hairStyle: 'short',
    cloth: '#e9edf5',
    clothAccent: 'rgba(34, 229, 255, 0.7)',
    label: 'BLEU NUIT NÉON',
    exif: '105mm · f/2.8 · ISO 200',
  },
};

type Props = {
  variant: ShotVariant;
  style?: React.CSSProperties;
  /** Affiche les repères « viewfinder » et l'EXIF. */
  hud?: boolean;
};

/** Maquette de photo de studio : décor, softbox, portrait, vignettage, grain et repères d'appareil. */
export const StudioShot: React.FC<Props> = ({variant, style, hud = true}) => {
  const frame = useCurrentFrame();
  const look = LOOKS[variant];
  const breathe = Math.sin(frame / 22) * 4;

  return (
    <div style={{position: 'relative', overflow: 'hidden', borderRadius: 40, background: look.backdrop, ...style}}>
      {variant === 'neon' && (
        <svg viewBox="0 0 400 500" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
          <circle cx="200" cy="215" r="150" fill="none" stroke="#22e5ff" strokeWidth="5" opacity="0.8" style={{filter: 'drop-shadow(0 0 14px #22e5ff)'}} />
          <circle cx="200" cy="215" r="176" fill="none" stroke="#ff2fb3" strokeWidth="2.5" opacity="0.55" />
        </svg>
      )}

      {/* faisceau de la softbox */}
      <div
        style={{
          position: 'absolute',
          left: '-18%',
          top: '-12%',
          width: '95%',
          height: '85%',
          background: `radial-gradient(ellipse at 20% 15%, ${look.key} 0%, transparent 62%)`,
          transform: 'rotate(-8deg)',
          filter: 'blur(14px)',
        }}
      />

      {/* sol */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: '38%', background: look.floor}} />

      {/* sujet */}
      <div style={{position: 'absolute', left: '9%', right: '9%', bottom: -8 + breathe * 0.4, height: '80%'}}>
        <Portrait
          uid={`shot-${variant}`}
          skin={look.skin}
          hair={look.hair}
          hairStyle={look.hairStyle}
          cloth={look.cloth}
          clothAccent={look.clothAccent}
          rim={look.rim}
        />
      </div>

      {/* vignettage */}
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 42%, transparent 52%, rgba(0,0,0,0.62) 100%)'}} />

      {/* grain argentique */}
      <svg width="100%" height="100%" style={{position: 'absolute', inset: 0, opacity: 0.16, mixBlendMode: 'overlay'}}>
        <filter id={`grain-${variant}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={variant.length} />
          <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain-${variant})`} />
      </svg>

      {hud && (
        <>
          {[
            {top: 22, left: 22, r: '0deg'},
            {top: 22, right: 22, r: '90deg'},
            {bottom: 22, right: 22, r: '180deg'},
            {bottom: 22, left: 22, r: '270deg'},
          ].map((c, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                width: 44,
                height: 44,
                top: c.top,
                bottom: c.bottom,
                left: c.left,
                right: c.right,
                borderTop: '4px solid rgba(255,255,255,0.8)',
                borderLeft: '4px solid rgba(255,255,255,0.8)',
                transform: `rotate(${c.r})`,
                borderTopLeftRadius: 8,
              }}
            />
          ))}
          <div
            style={{
              position: 'absolute',
              left: 28,
              bottom: 74,
              fontFamily: FONT_BODY,
              fontWeight: 800,
              fontSize: 23,
              letterSpacing: 3,
              color: 'rgba(255,255,255,0.9)',
              textShadow: '0 2px 10px rgba(0,0,0,0.9)',
            }}
          >
            {look.label}
          </div>
          <div
            style={{
              position: 'absolute',
              left: 28,
              bottom: 40,
              fontFamily: FONT_BODY,
              fontWeight: 500,
              fontSize: 20,
              letterSpacing: 1.5,
              color: 'rgba(255,255,255,0.7)',
              textShadow: '0 2px 10px rgba(0,0,0,0.9)',
            }}
          >
            {look.exif}
          </div>
        </>
      )}
    </div>
  );
};
