import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { KineticCaption } from "../components/KineticCaption";
import { PhotoCarousel } from "../components/PhotoCarousel";

export const ProofScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const metrics = [
    { value: "130", label: "Décors composites" },
    { value: "10", label: "Poses studio" },
    { value: "8", label: "Cadrages optiques" },
  ];

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "radial-gradient(circle at 50% 30%, #151928 0%, #08090C 80%)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "160px 40px",
        boxSizing: "border-box",
      }}
    >
      {/* Badge Compatibilité */}
      <div
        style={{
          display: "flex",
          gap: 16,
          backgroundColor: "rgba(255,255,255,0.08)",
          borderRadius: 30,
          padding: "12px 28px",
          color: "#E2E8F0",
          fontSize: 24,
          fontWeight: 700,
        }}
      >
        <span>⚡ Optimisé pour ChatGPT Images & Gemini</span>
      </div>

      {/* Vraies photos de rendu */}
      <PhotoCarousel width={560} height={700} firstStep={50} every={75} />

      {/* Compteurs / Métriques */}
      <div style={{ display: "flex", gap: 24, width: "100%", justifyContent: "center" }}>
        {metrics.map((m, i) => {
          const s = spring({ frame: frame - (10 + i * 12), fps });
          return (
            <div
              key={i}
              style={{
                transform: `scale(${s})`,
                backgroundColor: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 24,
                padding: "36px 30px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 12,
                flex: 1,
              }}
            >
              <span style={{ fontSize: 64, fontWeight: 900, color: "#00F0FF" }}>
                {m.value}
              </span>
              <span style={{ color: "#CBD5E1", fontSize: 22, textAlign: "center", fontWeight: 600 }}>
                {m.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Feature Box Retouche 2 Passes */}
      <div
        style={{
          width: "100%",
          maxWidth: 880,
          backgroundColor: "rgba(0, 240, 255, 0.08)",
          border: "2px dashed #00F0FF",
          borderRadius: 20,
          padding: "24px 32px",
          textAlign: "center",
          color: "#FFF",
          fontSize: 28,
          fontWeight: 700,
        }}
      >
        Workflow Pro en 2 passes : corrigez 1 détail sans toucher au visage
      </div>

      {/* Kinetic Subtitles */}
      <div style={{ minHeight: 180, display: "flex", alignItems: "center" }}>
        {frame < 180 ? (
          <KineticCaption
            text="Une infinité de variations avec la bibliothèque modulaire"
            highlightWords={["INFINITÉ", "MODULAIRE"]}
            highlightColor="#00F0FF"
          />
        ) : (
          <KineticCaption
            text="Fini les retouches compliquées, résultat instantané !"
            highlightWords={["INSTANTANÉ", "FINI"]}
            highlightColor="#38EF7D"
          />
        )}
      </div>
    </div>
  );
};
