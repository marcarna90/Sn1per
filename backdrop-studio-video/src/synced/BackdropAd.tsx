import React from 'react';
import {AbsoluteFill, Html5Audio, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background} from './components/Background';
import {Captions} from './components/Captions';
import {loadFonts} from '../fonts';
import {CtaScene} from './scenes/CtaScene';
import {ProblemScene} from './scenes/ProblemScene';
import {ProofScene} from './scenes/ProofScene';
import {RevealScene} from './scenes/RevealScene';
import {FONT_BODY} from '../theme';
import {AUDIO_TRACK, SCENE_OVERLAP, SCENES, SceneId} from './timeline';

loadFonts();

const SCENE_COMPONENTS: Record<SceneId, React.FC> = {
  problem: ProblemScene,
  reveal: RevealScene,
  proof: ProofScene,
  cta: CtaScene,
};

/** Fondu d'entrée/sortie : les scènes se recouvrent de SCENE_OVERLAP images pour un enchaînement fluide. */
const SceneFade: React.FC<{fadeIn: number; fadeOut: number; children: React.ReactNode}> = ({fadeIn, fadeOut, children}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const opacity =
    (fadeIn > 0 ? interpolate(frame, [0, fadeIn], [0, 1], {extrapolateRight: 'clamp'}) : 1) *
    (fadeOut > 0 ? interpolate(frame, [durationInFrames - fadeOut, durationInFrames], [1, 0], {extrapolateLeft: 'clamp'}) : 1);
  const scale = fadeIn > 0 ? interpolate(frame, [0, fadeIn + 4], [1.04, 1], {extrapolateRight: 'clamp'}) : 1;
  return <AbsoluteFill style={{opacity, transform: `scale(${scale})`}}>{children}</AbsoluteFill>;
};

export const BackdropAd: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONT_BODY, background: '#05040d'}}>
    <Background />

    {SCENES.map((s, i) => {
      const Scene = SCENE_COMPONENTS[s.id];
      const isLast = i === SCENES.length - 1;
      const overlap = isLast ? 0 : SCENE_OVERLAP;
      return (
        <Sequence key={s.id} from={s.from} durationInFrames={s.to - s.from + overlap} name={s.id}>
          <SceneFade fadeIn={i === 0 ? 0 : SCENE_OVERLAP} fadeOut={overlap}>
            <Scene />
          </SceneFade>
        </Sequence>
      );
    })}

    <Captions />

    {/* voix off : une seule piste, déjà calée image par image sur la timeline (scripts/generate_voice.py) */}
    {AUDIO_TRACK && <Html5Audio src={staticFile(AUDIO_TRACK)} volume={1} />}
  </AbsoluteFill>
);
