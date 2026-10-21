import {continueRender, delayRender, staticFile} from 'remotion';

const FACES = [
  {family: 'Bebas Neue', weight: '400', file: 'fonts/bebas-neue-latin-400-normal.woff2'},
  {family: 'Inter', weight: '500', file: 'fonts/inter-latin-500-normal.woff2'},
  {family: 'Inter', weight: '700', file: 'fonts/inter-latin-700-normal.woff2'},
  {family: 'Inter', weight: '800', file: 'fonts/inter-latin-800-normal.woff2'},
  {family: 'Inter', weight: '900', file: 'fonts/inter-latin-900-normal.woff2'},
];

let started = false;

/** Charge les polices locales (public/fonts) et bloque le rendu tant qu'elles ne sont pas prêtes. */
export const loadFonts = (): void => {
  if (started || typeof document === 'undefined') return;
  started = true;
  const handle = delayRender('Chargement des polices');
  Promise.all(
    FACES.map(async (f) => {
      const face = new FontFace(f.family, `url(${staticFile(f.file)}) format('woff2')`, {weight: f.weight});
      await face.load();
      document.fonts.add(face);
    }),
  )
    .catch((err) => console.error('Police non chargée', err))
    .finally(() => continueRender(handle));
};
