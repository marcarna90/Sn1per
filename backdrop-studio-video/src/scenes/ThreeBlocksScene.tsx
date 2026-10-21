import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { KineticCaption } from "../components/KineticCaption";
import { PhotoStrip } from "../components/PhotoStrip";

export const ThreeBlocksScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const blocks = [
    {
      num: "BLOC 1",
      title: "IDENTITY LOCK™ PRO",
      desc: "Verrouille traits, nez, yeux et carnation exacte",
      color: "#00F0FF",
      delay: 15,
    },
    {
      num: "BLOC 2",
      title: "130 DÉCORS DE STUDIO",
      desc: "Réécrits par des photographes professionnels",
      color: "#A855F7",
      delay: 100,
    },
    {
      num: "BLOC 3",
      title: "PHOTO PHYSIQUE",
      desc: "Lumières Pro 85mm + 10 indices de réalisme",
      color: "#FFD600",
      delay: 185,
    },
  ];

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "linear-gradient(180deg, #090B10 0%, #111422 100%)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "140px 40px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          border: "1px solid #00F0FF",
          color: "#00F0FF",
          padding: "12px 28px",
          borderRadius: 30,
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: 2,
        }}
      >
        LE NOUVEAU SYSTÈME
      </div>

      {/* Vraies photos : même visage, décors différents */}
      <PhotoStrip width={880} delay={10} stagger={12} accent="#00F0FF" />

      {/* Cartes des 3 blocs */}
      <div style={{ display: "flex", flexDirection: "column", gap: 24, width: "100%", maxWidth: 880 }}>
        {blocks.map((b, i) => {
          const cardSpring = spring({
            frame: frame - b.delay,
            fps,
            config: { damping: 13, stiffness: 160 },
          });
          const isActive = frame >= b.delay && frame < b.delay + 90;

          return (
            <div
              key={i}
              style={{
                transform: `scale(${Math.max(0, cardSpring)})`,
                backgroundColor: isActive ? `${b.color}18` : "rgba(255,255,255,0.04)",
                border: `2px solid ${isActive ? b.color : "rgba(255,255,255,0.15)"}`,
                borderRadius: 24,
                padding: "28px 36px",
                display: "flex",
                alignItems: "center",
                gap: 28,
                boxShadow: isActive ? `0 0 35px ${b.color}44` : "none",
              }}
            >
              <div
                style={{
                  backgroundColor: b.color,
                  color: "#000",
                  fontSize: 22,
                  fontWeight: 900,
                  padding: "10px 18px",
                  borderRadius: 12,
                }}
              >
                {b.num}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ color: "#FFF", fontSize: 34, fontWeight: 800 }}>
                  {b.title}
                </div>
                <div style={{ color: "rgba(255,255,255,0.7)", fontSize: 24 }}>
                  {b.desc}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Kinetic Subtitles */}
      <div style={{ minHeight: 180, display: "flex", alignItems: "center" }}>
        {frame < 120 ? (
          <KineticCaption
            text="Découvrez le moteur d'assemblage en 3 blocs"
            highlightWords={["3", "BLOCS", "MOTEUR"]}
            highlightColor="#00F0FF"
          />
        ) : frame < 240 ? (
          <KineticCaption
            text="Identity Lock préserve 100% de votre vrai visage"
            highlightWords={["IDENTITY", "LOCK", "100%"]}
            highlightColor="#A855F7"
          />
        ) : (
          <KineticCaption
            text="Un vrai rendu optique de studio photographique"
            highlightWords={["OPTIQUE", "STUDIO", "VRAI"]}
            highlightColor="#FFD600"
          />
        )}
      </div>
    </div>
  );
};
