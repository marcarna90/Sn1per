import {staticFile} from 'remotion';

export type PhotoKey = 'rose' | 'gold' | 'grey' | 'park';

export type Photo = {
  src: string;
  width: number;
  height: number;
  /** Centre du visage et largeur du visage, en fraction de l'image (sert aux recadrages ronds). */
  face: {x: number; y: number; w: number};
  /** object-position pour les cartes 4:5 (le parc, en 9:16, est recadré pour garder le visage). */
  position: string;
  decor: string;
  pose: string;
  cadrage: string;
};

/** Les 4 images fournies (public/images). */
export const PHOTOS: Record<PhotoKey, Photo> = {
  rose: {
    src: staticFile('images/rose.jpg'),
    width: 1122,
    height: 1402,
    face: {x: 0.57, y: 0.135, w: 0.18},
    position: 'center 30%',
    decor: 'ROSE POUDRÉ',
    pose: 'APPUYÉE',
    cadrage: 'PLEIN PIED',
  },
  gold: {
    src: staticFile('images/gold.jpg'),
    width: 1122,
    height: 1402,
    face: {x: 0.508, y: 0.403, w: 0.17},
    position: 'center 40%',
    decor: 'OR & BALLONS',
    pose: 'ASSISE',
    cadrage: 'PLAN LARGE',
  },
  grey: {
    src: staticFile('images/grey.jpg'),
    width: 1122,
    height: 1402,
    face: {x: 0.486, y: 0.214, w: 0.2},
    position: 'center 30%',
    decor: 'GRIS STUDIO',
    pose: 'SUR CHAISE',
    cadrage: 'PLAN AMÉRICAIN',
  },
  park: {
    src: staticFile('images/park.jpg'),
    width: 585,
    height: 1024,
    face: {x: 0.504, y: 0.21, w: 0.14},
    // Garde la tête et le buste : le bas (filigrane de l'outil de génération) sort du cadre.
    position: 'center 10%',
    decor: 'PARC URBAIN',
    pose: 'EN MOUVEMENT',
    cadrage: 'PLEIN PIED',
  },
};

export const PROOF_ORDER: PhotoKey[] = ['rose', 'gold', 'grey', 'park'];
