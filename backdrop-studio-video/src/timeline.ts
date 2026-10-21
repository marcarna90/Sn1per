import narration from './narration.json';
import generated from './timeline.generated.json';

export const FPS = 30;
export const WIDTH = 1080;
export const HEIGHT = 1920;
/** Images d'avance avant la première phrase, pour que le visuel soit en place. */
export const LEAD_FRAMES = 6;
/** Recouvrement entre deux scènes (fondu enchaîné). */
export const SCENE_OVERLAP = 8;

export type SceneId = 'problem' | 'reveal' | 'proof' | 'cta';
export type SegmentId = 'hook' | 'intro' | 'block1' | 'block2' | 'block3' | 'proof' | 'cta';

export type TimedSegment = {
  id: SegmentId;
  scene: SceneId;
  caption: string;
  /** Première image de la phrase (début de l'audio). */
  start: number;
  /** Images occupées par la voix. */
  speechFrames: number;
  /** Images réservées au segment (voix + respiration). */
  frames: number;
  /** Chemin dans public/ si l'audio a été généré, sinon null. */
  audioFile: string | null;
  /** true si la durée vient du mp3 réel, false si c'est la durée prévue. */
  measured: boolean;
};

type ManifestEntry = {file: string; durationSec: number};
const manifest = (generated as {segments: Record<string, ManifestEntry>}).segments;

const gapFrames = Math.round(narration.gapSec * FPS);
const tailFrames = Math.round(narration.tailSec * FPS);

let cursor = LEAD_FRAMES;

export const SEGMENTS: TimedSegment[] = narration.segments.map((s, i, all) => {
  const entry = manifest[s.id];
  const speechSec = entry ? entry.durationSec : s.fallbackSec;
  const speechFrames = Math.ceil(speechSec * FPS);
  const frames = speechFrames + (i === all.length - 1 ? tailFrames : gapFrames);
  const seg: TimedSegment = {
    id: s.id as SegmentId,
    scene: s.scene as SceneId,
    caption: s.caption,
    start: cursor,
    speechFrames,
    frames,
    audioFile: entry ? entry.file : null,
    measured: Boolean(entry),
  };
  cursor += frames;
  return seg;
});

export const TOTAL_FRAMES = cursor;

export const segment = (id: SegmentId): TimedSegment => {
  const found = SEGMENTS.find((s) => s.id === id);
  if (!found) throw new Error(`Segment inconnu : ${id}`);
  return found;
};

export type SceneRange = {
  id: SceneId;
  from: number;
  to: number;
  segments: TimedSegment[];
};

const SCENE_ORDER: SceneId[] = ['problem', 'reveal', 'proof', 'cta'];

export const SCENES: SceneRange[] = SCENE_ORDER.map((id, i) => {
  const segments = SEGMENTS.filter((s) => s.scene === id);
  const last = segments[segments.length - 1];
  return {
    id,
    from: i === 0 ? 0 : segments[0].start,
    to: last.start + last.frames,
    segments,
  };
});

export const scene = (id: SceneId): SceneRange => {
  const found = SCENES.find((s) => s.id === id);
  if (!found) throw new Error(`Scène inconnue : ${id}`);
  return found;
};

/** Couleur d'accent des sous-titres selon le segment. */
export const SEGMENT_ACCENT: Record<SegmentId, string> = {
  hook: '#ff3b5c',
  intro: '#22e5ff',
  block1: '#22e5ff',
  block2: '#ff2fb3',
  block3: '#ffc85a',
  proof: '#ffc85a',
  cta: '#22e5ff',
};
