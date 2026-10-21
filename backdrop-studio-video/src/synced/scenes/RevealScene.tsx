import React from 'react';
import {Img, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FaceCrop} from '../../components/FaceCrop';
import {LightIcon, LockIcon, SceneIcon} from '../../components/Icons';
import {PhotoKey, PHOTOS} from '../../images';
import {C, FONT_BODY, FONT_DISPLAY} from '../../theme';
import {scene, segment, SegmentId} from '../timeline';

const CARD_W = 960;
const CARD_H = 270;
const GAP = 28;
const TOP = 410;

type Block = {
  seg: SegmentId;
  n: string;
  title: string;
  sub: string;
  color: string;
  Icon: React.FC<{size?: number; color?: string}>;
  counter: {to: number; suffix: string; label: string};
  extra: 'tag' | 'thumbs' | 'lights';
};

const BLOCKS: Block[] = [
  {
    seg: 'block1',
    n: '01',
    title: 'IDENTITY LOCK™ PRO',
    sub: 'Verrouille traits, nez, yeux et carnation exacte',
    color: C.cyan,
    Icon: LockIcon,
    counter: {to: 100, suffix: '%', label: 'VERROUILLÉ'},
    extra: 'tag',
  },
  {
    seg: 'block2',
    n: '02',
    title: 'SCÈNE',
    sub: 'Réécrits par des photographes professionnels',
    color: C.magenta,
    Icon: SceneIcon,
    counter: {to: 130, suffix: '', label: 'DÉCORS'},
    extra: 'thumbs',
  },
  {
    seg: 'block3',
    n: '03',
    title: 'PHOTO PHYSIQUE',
    sub: 'Lumières Pro 85mm + 10 indices de réalisme',
    color: C.gold,
    Icon: LightIcon,
    counter: {to: 10, suffix: '', label: 'INDICES'},
    extra: 'lights',
  },
];

const FACES: PhotoKey[] = ['rose', 'gold', 'grey'];
const THUMBS: PhotoKey[] = ['rose', 'gold', 'grey', 'park'];

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const RevealScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sc = scene('reveal');
  const rel = (id: SegmentId) => segment(id).start - sc.from;

  const head = spring({frame, fps, config: {damping: 13, stiffness: 150}});
  const lastEnd = rel('block3') + segment('block3').frames;
  const finale = interpolate(frame, [lastEnd - 40, lastEnd - 10], [0, 1], clamp);

  return (
    <div style={{position: 'absolute', inset: 0}}>
      {/* titre */}
      <div
        style={{
          position: 'absolute',
          top: 112,
          left: 0,
          right: 0,
          textAlign: 'center',
          opacity: head,
          transform: `translateY(${(1 - head) * -60}px) scale(${0.85 + 0.15 * head})`,
        }}
      >
        <div style={{fontFamily: FONT_BODY, fontWeight: 800, fontSize: 28, letterSpacing: 9, color: C.cyan, marginBottom: 6}}>
          LE NOUVEAU SYSTÈME
        </div>
        <div style={{fontFamily: FONT_DISPLAY, fontSize: 124, lineHeight: 0.92, color: C.white, textShadow: `0 0 40px ${C.cyan}77`}}>
          MOTEUR D&apos;ASSEMBLAGE
        </div>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 150,
            lineHeight: 0.95,
            backgroundImage: `linear-gradient(90deg, ${C.cyan}, ${C.magenta} 55%, ${C.gold})`,
            WebkitBackgroundClip: 'text',
            color: 'transparent',
          }}
        >
          EN 3 BLOCS
        </div>
      </div>

      {/* connecteurs entre les blocs */}
      {[0, 1].map((i) => {
        const on = frame >= rel(BLOCKS[i + 1].seg);
        const grow = interpolate(frame, [rel(BLOCKS[i + 1].seg), rel(BLOCKS[i + 1].seg) + 10], [0, 1], clamp);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: 120 - 4,
              top: TOP + (i + 1) * CARD_H + i * GAP,
              width: 8,
              height: GAP,
              background: `linear-gradient(180deg, ${BLOCKS[i].color}, ${BLOCKS[i + 1].color})`,
              transform: `scaleY(${on ? grow : 0})`,
              transformOrigin: 'top',
              boxShadow: `0 0 18px ${BLOCKS[i + 1].color}`,
              zIndex: 2,
            }}
          />
        );
      })}

      {BLOCKS.map((b, i) => {
        const start = rel(b.seg);
        const end = start + segment(b.seg).frames;
        const enter = spring({frame: frame - (start - 3), fps, config: {damping: 13, stiffness: 140, mass: 0.8}});
        const active = frame >= start && frame < end;
        const activeP = interpolate(frame, [start, start + 8, end - 6, end], [0, 1, 1, 0], clamp);
        const count = Math.round(interpolate(frame, [start + 4, start + 40], [0, b.counter.to], clamp));
        const fromX = i % 2 === 0 ? -760 : 760;
        const dim = frame >= end ? 0.78 : 1;
        const scale = 1 + 0.035 * activeP + 0.02 * finale * Math.sin(frame / 5);
        const borderColor = finale > 0.1 ? `rgba(255,255,255,${0.2 + 0.5 * finale})` : active ? b.color : C.glassBorder;

        const slotTop = TOP + i * (CARD_H + GAP);

        return (
          <React.Fragment key={b.seg}>
          {/* emplacement vide : annonce les 3 blocs à assembler avant qu'ils n'arrivent */}
          <div
            style={{
              position: 'absolute',
              left: (1080 - CARD_W) / 2,
              top: slotTop,
              width: CARD_W,
              height: CARD_H,
              boxSizing: 'border-box',
              display: 'flex',
              alignItems: 'center',
              padding: '0 30px',
              gap: 22,
              borderRadius: 34,
              border: `3px dashed ${b.color}55`,
              background: 'rgba(255,255,255,0.025)',
              opacity: Math.max(0, 1 - enter) * head,
            }}
          >
            <div
              style={{
                width: 136,
                textAlign: 'center',
                fontFamily: FONT_DISPLAY,
                fontSize: 150,
                lineHeight: 1,
                color: 'transparent',
                WebkitTextStroke: `3px ${b.color}55`,
              }}
            >
              {b.n}
            </div>
            <div style={{flex: 1}}>
              <div style={{height: 34, width: 300, borderRadius: 12, background: 'rgba(255,255,255,0.08)'}} />
              <div style={{height: 20, width: 430, borderRadius: 10, background: 'rgba(255,255,255,0.05)', marginTop: 18}} />
              <div style={{height: 20, width: 340, borderRadius: 10, background: 'rgba(255,255,255,0.05)', marginTop: 12}} />
            </div>
          </div>
          <div
            style={{
              position: 'absolute',
              left: (1080 - CARD_W) / 2,
              top: slotTop,
              width: CARD_W,
              height: CARD_H,
              display: 'flex',
              alignItems: 'center',
              padding: '0 30px',
              gap: 22,
              borderRadius: 34,
              background: `linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.03)), rgba(10,8,28,0.82)`,
              border: `3px solid ${borderColor}`,
              boxShadow: `0 0 ${20 + 60 * activeP}px ${b.color}${active ? '88' : '33'}, inset 0 0 40px ${b.color}${active ? '22' : '0d'}`,
              opacity: Math.min(1, enter) * dim,
              transform: `translateX(${(1 - enter) * fromX}px) scale(${scale})`,
            }}
          >
            {/* numéro */}
            <div
              style={{
                width: 136,
                fontFamily: FONT_DISPLAY,
                fontSize: 150,
                lineHeight: 1,
                color: 'transparent',
                WebkitTextStroke: `3px ${b.color}`,
                textShadow: `0 0 26px ${b.color}`,
                textAlign: 'center',
              }}
            >
              {b.n}
            </div>

            {/* texte */}
            <div style={{flex: 1, minWidth: 0}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
                <b.Icon size={46} color={b.color} />
                <span style={{fontFamily: FONT_DISPLAY, fontSize: 64, lineHeight: 1, color: C.white, whiteSpace: 'nowrap'}}>{b.title}</span>
              </div>
              <div style={{fontFamily: FONT_BODY, fontWeight: 600, fontSize: 27, lineHeight: 1.25, color: C.mute, marginTop: 10}}>{b.sub}</div>

              {b.extra === 'tag' && (
                <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 12}}>
                  <div
                    style={{
                      padding: '7px 18px',
                      borderRadius: 999,
                      border: `2px solid ${b.color}`,
                      fontFamily: FONT_BODY,
                      fontWeight: 800,
                      fontSize: 22,
                      letterSpacing: 3,
                      color: b.color,
                    }}
                  >
                    SANS DÉFORMATION
                  </div>
                  {/* même visage, trois décors */}
                  <div style={{display: 'flex'}}>
                    {FACES.map((k, n) => {
                      const pop = spring({frame: frame - (start + 10 + n * 7), fps, config: {damping: 10, stiffness: 220, mass: 0.6}});
                      return <FaceCrop key={k} photo={k} size={58} ringColor={b.color} style={{marginLeft: n ? -14 : 0, transform: `scale(${pop})`, zIndex: 3 - n}} />;
                    })}
                  </div>
                </div>
              )}
              {b.extra === 'thumbs' && (
                <div style={{display: 'flex', gap: 10, marginTop: 14}}>
                  {THUMBS.map((k, n) => {
                    const pop = spring({frame: frame - (start + 12 + n * 7), fps, config: {damping: 10, stiffness: 220, mass: 0.6}});
                    return (
                      <div
                        key={k}
                        style={{
                          position: 'relative',
                          width: 74,
                          height: 74,
                          borderRadius: 16,
                          overflow: 'hidden',
                          border: `3px solid ${b.color}`,
                          boxShadow: `0 0 16px ${b.color}88`,
                          transform: `scale(${pop})`,
                        }}
                      >
                        <Img src={PHOTOS[k].src} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 30%'}} />
                      </div>
                    );
                  })}
                </div>
              )}
              {b.extra === 'lights' && (
                <div style={{display: 'flex', gap: 12, marginTop: 14}}>
                  {['A', 'B', 'C', 'D'].map((l, k) => {
                    const on = frame >= start + 14 + k * 9;
                    const pop = spring({frame: frame - (start + 14 + k * 9), fps, config: {damping: 9, stiffness: 240, mass: 0.5}});
                    return (
                      <div
                        key={l}
                        style={{
                          width: 52,
                          height: 52,
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontFamily: FONT_DISPLAY,
                          fontSize: 38,
                          color: on ? '#1a1200' : C.mute,
                          background: on ? b.color : 'transparent',
                          border: `2px solid ${on ? b.color : C.glassBorder}`,
                          boxShadow: on ? `0 0 22px ${b.color}` : 'none',
                          transform: `scale(${on ? 0.8 + 0.2 * pop : 1})`,
                        }}
                      >
                        {l}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* compteur */}
            <div style={{width: 200, textAlign: 'center'}}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 132,
                  lineHeight: 0.9,
                  color: b.color,
                  textShadow: `0 0 30px ${b.color}99`,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {count}
                <span style={{fontSize: 70}}>{b.counter.suffix}</span>
              </div>
              <div style={{fontFamily: FONT_BODY, fontWeight: 800, fontSize: 20, letterSpacing: 3, color: C.mute, marginTop: 6}}>{b.counter.label}</div>
            </div>
          </div>
          </React.Fragment>
        );
      })}
    </div>
  );
};
