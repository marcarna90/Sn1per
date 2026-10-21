import React from 'react';

export type HairStyle = 'short' | 'afro' | 'long';

type Props = {
  /** Identifiant unique : évite les collisions d'ids de dégradés SVG entre plusieurs portraits. */
  uid: string;
  skin: [string, string];
  hair: string;
  hairStyle?: HairStyle;
  cloth: string;
  clothAccent?: string;
  /** Couleur de la lumière de contour. */
  rim?: string;
  /** Rendu « cire » : aplats lisses, reflets spéculaires, aucune ombre de volume. */
  plastic?: boolean;
  /** 0 = visage fidèle, 1 = traits déformés. */
  distort?: number;
  style?: React.CSSProperties;
};

/** Portrait vectoriel stylisé (buste + visage), utilisé pour les maquettes. */
export const Portrait: React.FC<Props> = ({
  uid,
  skin,
  hair,
  hairStyle = 'short',
  cloth,
  clothAccent = 'rgba(255,255,255,0.18)',
  rim,
  plastic = false,
  distort = 0,
  style,
}) => {
  const d = distort;
  const headRx = 80 + 20 * d;
  const headRy = 98 - 12 * d;

  // Yeux : fidèles à d=0, asymétriques à d>0.
  const eyeL = {cx: 164 - 4 * d, cy: 214 - 8 * d, rx: 15 + 7 * d, ry: 8 + 9 * d};
  const eyeR = {cx: 236 + 6 * d, cy: 214 + 12 * d, rx: 15 - 4 * d, ry: 8 - 2 * d};
  const mouthW = 26 + 14 * d;
  const mouthY = 278 + 4 * d;
  const mouthSkew = 14 * d;

  return (
    <svg viewBox="0 0 400 500" style={{width: '100%', height: '100%', overflow: 'visible', ...style}}>
      <defs>
        <radialGradient id={`${uid}-face`} cx="42%" cy="34%" r="75%">
          <stop offset="0%" stopColor={skin[0]} />
          <stop offset={plastic ? '100%' : '72%'} stopColor={plastic ? skin[0] : skin[1]} />
          <stop offset="100%" stopColor={skin[1]} />
        </radialGradient>
        <linearGradient id={`${uid}-neck`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={skin[1]} />
          <stop offset="100%" stopColor={skin[1]} stopOpacity="0.85" />
        </linearGradient>
        <linearGradient id={`${uid}-cloth`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={cloth} />
          <stop offset="100%" stopColor="#000" stopOpacity="0.55" />
        </linearGradient>
        <radialGradient id={`${uid}-spec`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff" stopOpacity={plastic ? 0.95 : 0.35} />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <filter id={`${uid}-soft`}>
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>

      {/* cheveux derrière la tête */}
      {hairStyle === 'afro' && <ellipse cx="200" cy="170" rx="128" ry="118" fill={hair} />}
      {hairStyle === 'long' && <path d="M104 190 C86 300 96 400 70 470 L330 470 C304 400 314 300 296 190 Z" fill={hair} />}

      {/* buste */}
      <path d="M6 500 C14 410 96 366 156 350 L244 350 C304 366 386 410 394 500 Z" fill={`url(#${uid}-cloth)`} />
      <path d="M156 350 L200 438 L244 350" fill="none" stroke={clothAccent} strokeWidth="5" strokeLinejoin="round" />
      <path d="M186 372 L200 438 L214 372 Z" fill={skin[1]} />

      {/* cou */}
      <path d="M168 280 L168 352 Q200 392 232 352 L232 280 Z" fill={`url(#${uid}-neck)`} />
      {!plastic && <path d="M168 330 Q200 372 232 330 L232 352 Q200 392 168 352 Z" fill="#000" opacity="0.22" />}

      {/* oreilles */}
      <ellipse cx={200 - headRx + 4} cy={232} rx="13" ry="25" fill={skin[1]} />
      <ellipse cx={200 + headRx - 4} cy={232} rx="13" ry="25" fill={skin[1]} />

      {/* visage */}
      <ellipse cx="200" cy="226" rx={headRx} ry={headRy} fill={`url(#${uid}-face)`} />

      {/* cheveux devant */}
      {hairStyle === 'short' && (
        <path d="M118 206 C104 116 168 82 204 82 C250 82 304 116 284 206 C274 170 248 150 204 150 C160 150 130 172 118 206 Z" fill={hair} />
      )}
      {hairStyle === 'afro' && (
        <path d="M120 196 C122 146 160 130 200 130 C242 130 280 146 280 196 C262 170 238 158 200 158 C162 158 138 170 120 196 Z" fill={hair} />
      )}
      {hairStyle === 'long' && (
        <path d="M112 214 C92 110 176 78 206 78 C256 78 312 116 288 214 C282 168 252 144 204 144 C160 144 124 170 112 214 Z" fill={hair} />
      )}

      {/* sourcils */}
      <path d={`M${eyeL.cx - 20} ${eyeL.cy - 22 - 6 * d} Q${eyeL.cx} ${eyeL.cy - 32 - 12 * d} ${eyeL.cx + 20} ${eyeL.cy - 22}`} stroke={hair} strokeWidth="6" strokeLinecap="round" fill="none" opacity="0.9" />
      <path d={`M${eyeR.cx - 20} ${eyeR.cy - 22} Q${eyeR.cx} ${eyeR.cy - 32 + 6 * d} ${eyeR.cx + 20} ${eyeR.cy - 22 + 10 * d}`} stroke={hair} strokeWidth="6" strokeLinecap="round" fill="none" opacity="0.9" />

      {/* yeux */}
      {[eyeL, eyeR].map((e, i) => (
        <g key={i}>
          <ellipse cx={e.cx} cy={e.cy} rx={e.rx} ry={e.ry} fill="#f4f0ea" />
          <circle cx={e.cx + (i ? -1 : 1)} cy={e.cy} r={Math.min(e.ry, 7.5) + 0.5} fill="#2a1a12" />
          <circle cx={e.cx + 3} cy={e.cy - 2} r="2" fill="#fff" />
        </g>
      ))}

      {/* nez */}
      {!plastic && <path d="M200 224 Q191 258 184 264 Q200 274 216 264" fill="none" stroke={skin[1]} strokeWidth="5" strokeLinecap="round" opacity="0.85" />}
      {plastic && <path d="M200 232 Q196 256 192 262 Q200 268 208 262" fill="none" stroke={skin[1]} strokeWidth="3" strokeLinecap="round" opacity="0.45" />}

      {/* bouche */}
      <path
        d={`M${200 - mouthW} ${mouthY + mouthSkew} Q200 ${mouthY - 8} ${200 + mouthW} ${mouthY - mouthSkew} Q200 ${mouthY + 22 + 8 * d} ${200 - mouthW} ${mouthY + mouthSkew} Z`}
        fill="#8d2f3d"
        opacity="0.92"
      />
      <path d={`M${200 - mouthW + 4} ${mouthY + mouthSkew * 0.6} Q200 ${mouthY + 2} ${200 + mouthW - 4} ${mouthY - mouthSkew * 0.6}`} stroke="#4a1019" strokeWidth="2.2" fill="none" opacity="0.8" />

      {/* joues */}
      {!plastic && <circle cx="140" cy="262" r="20" fill="#e0567a" opacity="0.12" />}
      {!plastic && <circle cx="260" cy="262" r="20" fill="#e0567a" opacity="0.12" />}

      {/* reflets « plastique » */}
      {plastic && (
        <>
          <ellipse cx="170" cy="168" rx="46" ry="30" fill={`url(#${uid}-spec)`} />
          <ellipse cx="238" cy="250" rx="30" ry="40" fill={`url(#${uid}-spec)`} />
          <ellipse cx="200" cy="136" rx="26" ry="12" fill={`url(#${uid}-spec)`} />
        </>
      )}

      {/* lumière de contour */}
      {rim && (
        <g filter={`url(#${uid}-soft)`} opacity="0.9">
          <path d={`M${200 + headRx + 5} 196 C${200 + headRx + 12} 250 ${200 + headRx - 4} 292 ${200 + headRx - 30} 322`} stroke={rim} strokeWidth="5" fill="none" strokeLinecap="round" />
          <path d="M296 352 C340 372 380 410 392 470" stroke={rim} strokeWidth="6" fill="none" strokeLinecap="round" />
        </g>
      )}
    </svg>
  );
};
