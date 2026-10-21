import React from 'react';

type IconProps = {size?: number; color?: string; strokeWidth?: number};

const base = (size: number) => ({width: size, height: size, viewBox: '0 0 48 48', fill: 'none' as const});

export const LockIcon: React.FC<IconProps> = ({size = 64, color = '#fff', strokeWidth = 3.4}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="21" width="30" height="21" rx="5" />
    <path d="M15 21v-6a9 9 0 0 1 18 0v6" />
    <circle cx="24" cy="31" r="2.6" fill={color} />
    <path d="M24 33.5v4" />
  </svg>
);

export const SceneIcon: React.FC<IconProps> = ({size = 64, color = '#fff', strokeWidth = 3.4}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="9" width="38" height="30" rx="5" />
    <path d="M5 31l11-10 9 8 6-5 12 9" />
    <circle cx="33" cy="17" r="3" />
  </svg>
);

export const LightIcon: React.FC<IconProps> = ({size = 64, color = '#fff', strokeWidth = 3.4}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="24" cy="24" r="8" />
    <path d="M24 5v6M24 37v6M5 24h6M37 24h6M10.6 10.6l4.2 4.2M33.2 33.2l4.2 4.2M10.6 37.4l4.2-4.2M33.2 14.8l4.2-4.2" />
  </svg>
);

export const CheckIcon: React.FC<IconProps> = ({size = 48, color = '#fff', strokeWidth = 5}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="24" cy="24" r="19" />
    <path d="M15 25l6 6 12-13" />
  </svg>
);

export const ArrowIcon: React.FC<IconProps> = ({size = 64, color = '#fff', strokeWidth = 5}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 24h30" />
    <path d="M26 11l13 13-13 13" />
  </svg>
);

export const AlertIcon: React.FC<IconProps> = ({size = 48, color = '#fff', strokeWidth = 3.6}) => (
  <svg {...base(size)} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <path d="M24 6L44 41H4z" />
    <path d="M24 19v11" />
    <circle cx="24" cy="35" r="1.4" fill={color} />
  </svg>
);

export const CursorIcon: React.FC<IconProps> = ({size = 56, color = '#fff'}) => (
  <svg {...base(size)} fill={color}>
    <path d="M12 6l25 19-11 2.5 6 12-5 2.5-6-12.5L12 38z" stroke="#000" strokeWidth="1.6" strokeLinejoin="round" />
  </svg>
);
