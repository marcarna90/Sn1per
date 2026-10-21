import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { KineticCaption } from "../components/KineticCaption";
import { PhotoStrip } from "../components/PhotoStrip";

export const CtaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const ctaSpring = spring({ frame, fps, config: { damping: 10, stiffness: 180 } });
  const pulse = Math.sin(frame / 5) * 0.04 + 1;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "radial-gradient(circle at center, #19142E 0%, #07070A 80%)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "160px 40px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          color: "#FFD600",
          fontSize: 32,
          fontWeight: 900,
          letterSpacing: 3,
        }}
      >
        BACKDROP STUDIO™ PRO
      </div>

      {/* Vraies photos */}
      <PhotoStrip width={920} delay={5} stagger={8} accent="#FFD600" />

      {/* Bloc Offre & Boutique */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 32,
          width: "100%",
          maxWidth: 920,
        }}
      >
        <div style={{ color: "#FFF", fontSize: 48, fontWeight: 900, textAlign: "center" }}>
          TÉLÉCHARGEZ LE PACK COMPLET
        </div>

        {/* Bouton Lien Boutique */}
        <div
          style={{
            transform: `scale(${ctaSpring * pulse})`,
            backgroundColor: "#FFD600",
            color: "#000000",
            borderRadius: 30,
            padding: "36px 48px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            boxShadow: "0 0 60px rgba(255, 214, 0, 0.5)",
            width: "100%",
            boxSizing: "border-box",
          }}
        >
          <span style={{ fontSize: 28, fontWeight: 800, textTransform: "uppercase" }}>
            👉 Disponible sur la boutique :
          </span>
          <span
            style={{
              fontSize: 48,
              fontWeight: 900,
              letterSpacing: 1,
              fontFamily: "monospace",
              textDecoration: "underline",
            }}
          >
            rontsr.mychariow.shop
          </span>
        </div>

        <div style={{ color: "rgba(255,255,255,0.6)", fontSize: 24, fontWeight: 600 }}>
          Accès immédiat · 130 Décors · Moteur d'assemblage unique
        </div>
      </div>

      {/* Kinetic Subtitles */}
      <div style={{ minHeight: 180, display: "flex", alignItems: "center" }}>
        <KineticCaption
          text="Cliquez sur le lien et transformez vos photos maintenant !"
          highlightWords={["LIEN", "TRANSFORMEZ", "MAINTENANT"]}
          highlightColor="#FFD600"
        />
      </div>
    </div>
  );
};
