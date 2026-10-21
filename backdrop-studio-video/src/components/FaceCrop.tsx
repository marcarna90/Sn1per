import React from 'react';
import {Img} from 'remotion';
import {PhotoKey, PHOTOS} from '../images';

type Props = {
  photo: PhotoKey;
  size: number;
  ringColor: string;
  style?: React.CSSProperties;
};

/** Recadrage rond centré sur le visage (le visage occupe ~75 % du diamètre). */
export const FaceCrop: React.FC<Props> = ({photo, size, ringColor, style}) => {
  const p = PHOTOS[photo];
  const imgW = (size * 0.75) / p.face.w;
  const imgH = imgW * (p.height / p.width);

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '50%',
        overflow: 'hidden',
        border: `3px solid ${ringColor}`,
        boxShadow: `0 0 18px ${ringColor}99`,
        background: '#0a0714',
        flexShrink: 0,
        ...style,
      }}
    >
      <Img
        src={p.src}
        style={{
          position: 'absolute',
          width: imgW,
          height: imgH,
          left: size / 2 - p.face.x * imgW,
          top: size / 2 - p.face.y * imgH,
          maxWidth: 'none',
        }}
      />
    </div>
  );
};
