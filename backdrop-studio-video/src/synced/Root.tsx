import React from 'react';
import {Composition} from 'remotion';
import {BackdropAd} from './BackdropAd';
import {FPS, HEIGHT, TOTAL_FRAMES, WIDTH} from './timeline';

export const SyncedRoot: React.FC = () => (
  <Composition
    id="BackdropAd"
    component={BackdropAd}
    width={WIDTH}
    height={HEIGHT}
    fps={FPS}
    durationInFrames={TOTAL_FRAMES}
  />
);
