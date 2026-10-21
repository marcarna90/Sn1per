import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { KineticCaption } from "../components/KineticCaption";
import { DegradedPhoto } from "../components/DegradedPhoto";

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const badgeSpring = spring({ frame, fps, config: { damping: 10 } });
  const pulse = Math.sin(frame / 6) * 0.05 + 1;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "radial-gradient(circle at center, #260A10 0%, #0A0A0D 75%)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "160px 40px",
        boxSizing: "border-box",
      }}
    >
      {/* Alerte / Badge Frustration */}
      <div
        style={{
          transform: `scale(${badgeSpring * pulse})`,
          backgroundColor: "#FF2A55",
          color: "#FFFFFF",
          padding: "16px 36px",
          borderRadius: 40,
          fontSize: 32,
          fontWeight: 900,
          letterSpacing: 2,
          boxShadow: "0 0 40px rgba(255,42,85,0.6)",
        }}
      >
        ⚠️ STOP AUX PORTRAITS RATÉS
      </div>

      {/* Vraie photo qui se dégrade comme un mauvais rendu IA */}
      <DegradedPhoto width={720} height={900} start={10} filterId="degrade-warp" />

      {/* Cartes d'erreurs IA classiques */}
      <div style={{ display: "flex", gap: 24, width: "100%", justifyContent: "center" }}>
        {[
          { icon: "❌", label: "Peau en plastique" },
          { icon: "❌", label: "Visage déformé" },
          { icon: "❌", label: "Éclairage fake" },
        ].map((item, i) => {
          const cardSpring = spring({
            frame: frame - (20 + i * 15),
            fps,
            config: { damping: 14 },
          });
          return (
            <div
              key={i}
              style={{
                transform: `scale(${cardSpring})`,
                backgroundColor: "rgba(255, 42, 85, 0.12)",
                border: "2px solid rgba(255, 42, 85, 0.4)",
                borderRadius: 24,
                padding: "24px 28px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 44 }}>{item.icon}</span>
              <span style={{ color: "#FFF", fontSize: 26, fontWeight: 700 }}>
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Kinetic Subtitles */}
      <div style={{ minHeight: 180, display: "flex", alignItems: "center" }}>
        {frame < 90 ? (
          <KineticCaption
            text="Arrêtez de ruiner vos portraits avec l'IA !"
            highlightWords={["RUINER", "PORTRAITS"]}
            highlightColor="#FF2A55"
          />
        ) : (
          <KineticCaption
            text="Toujours le même résultat en plastique méconnaissable ?"
            highlightWords={["PLASTIQUE", "MÉCONNAISSABLE"]}
            highlightColor="#FFB800"
          />
        )}
      </div>
    </div>
  );
};
