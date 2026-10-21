import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, FONT_BODY} from '../../theme';
import {SEGMENTS, SEGMENT_ACCENT, TimedSegment} from '../timeline';

type Word = {text: string; hot: boolean};
type Phrase = {words: Word[]; chars: number; pause: number; small: boolean};

/** "Tes portraits|déforment ton *visage* ?" → phrases → mots (les *mots* sont mis en valeur). */
const parseCaption = (caption: string): Phrase[] =>
  caption.split('|').map((rawPhrase) => {
    // « ~ » en tête : phrase en petits caractères et casse d'origine (utile pour une URL).
    const small = rawPhrase.startsWith('~');
    const raw = small ? rawPhrase.slice(1) : rawPhrase;
    const words: Word[] = [];
    raw.split('*').forEach((part, i) => {
      part
        .split(/\s+/)
        .filter(Boolean)
        .forEach((text) => words.push({text, hot: i % 2 === 1}));
    });
    const plain = words.map((w) => w.text).join(' ');
    // Les ponctuations fortes sont suivies d'une pause à l'oral : on leur donne un peu plus de temps.
    const pause = /[.?!:,…]$/.test(plain) ? 7 : 2;
    return {words, chars: plain.length, pause, small};
  });

/** Répartit la durée parlée du segment entre les phrases, au prorata des caractères + pauses. */
const phraseTimings = (seg: TimedSegment, phrases: Phrase[]) => {
  const lead = 3; // le mp3 démarre avec un très court silence
  const span = Math.max(1, seg.speechFrames - lead);
  const weights = phrases.map((p) => p.chars + p.pause);
  const total = weights.reduce((a, b) => a + b, 0);
  let acc = 0;
  return phrases.map((p, i) => {
    const from = seg.start + lead + Math.round((acc / total) * span);
    acc += weights[i];
    const to = i === phrases.length - 1 ? seg.start + seg.frames : seg.start + lead + Math.round((acc / total) * span);
    return {phrase: p, from, to};
  });
};

const TIMINGS = SEGMENTS.map((seg) => ({seg, phrases: phraseTimings(seg, parseCaption(seg.caption))}));

type Props = {
  /** Position verticale du bloc de sous-titres. */
  y?: number;
  fontSize?: number;
};

export const Captions: React.FC<Props> = ({y = 1310, fontSize = 76}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const entry = TIMINGS.find(({seg}) => frame >= seg.start && frame < seg.start + seg.frames);
  if (!entry) return null;
  const current = entry.phrases.find((p) => frame >= p.from && frame < p.to);
  if (!current) return null;

  const accent = SEGMENT_ACCENT[entry.seg.id];
  const local = frame - current.from;
  const dur = current.to - current.from;
  const exit = interpolate(frame, [current.to - 5, current.to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const stagger = Math.min(4, Math.max(2, Math.floor((dur * 0.4) / current.phrase.words.length)));

  return (
    <div
      style={{
        position: 'absolute',
        left: 56,
        right: 56,
        top: y,
        minHeight: 260,
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignContent: 'flex-start',
        gap: `0 ${Math.round((current.phrase.small ? fontSize * 0.72 : fontSize) * 0.22)}px`,
        fontFamily: FONT_BODY,
        fontWeight: 900,
        fontSize: current.phrase.small ? Math.round(fontSize * 0.72) : fontSize,
        lineHeight: 1.08,
        letterSpacing: -1.5,
        textTransform: current.phrase.small ? 'none' : 'uppercase',
        textAlign: 'center',
        opacity: exit,
        transform: `translateY(${(1 - exit) * -14}px)`,
      }}
    >
      {current.phrase.words.map((w, i) => {
        const p = spring({frame: local - i * stagger, fps, config: {damping: 11, stiffness: 190, mass: 0.55}});
        return (
          <span
            key={`${current.from}-${i}`}
            style={{
              display: 'inline-block',
              color: w.hot ? accent : C.white,
              opacity: interpolate(p, [0, 0.4], [0, 1], {extrapolateRight: 'clamp'}),
              transform: `translateY(${(1 - p) * 46}px) scale(${0.55 + 0.45 * p})`,
              textShadow: w.hot
                ? `0 0 28px ${accent}99, 0 6px 22px rgba(0,0,0,0.85)`
                : '0 6px 22px rgba(0,0,0,0.9), 0 0 3px rgba(0,0,0,0.9)',
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
