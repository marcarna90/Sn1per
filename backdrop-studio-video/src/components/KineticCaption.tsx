import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

interface KineticCaptionProps {
  text: string;
  highlightWords?: string[];
  highlightColor?: string;
}

export const KineticCaption: React.FC<KineticCaptionProps> = ({
  text,
  highlightWords = [],
  highlightColor = "#FFD600",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: "14px 20px",
        padding: "0 60px",
        maxWidth: 1000,
      }}
    >
      {words.map((word, index) => {
        const cleanWord = word.replace(/[^a-zA-Z0-9À-ÿ™]/g, "").toUpperCase();
        const isHighlighted = highlightWords.some(
          (hw) => hw.toUpperCase() === cleanWord
        );

        const wordDelay = index * 2.5;
        const wordSpring = spring({
          frame: frame - wordDelay,
          fps,
          config: { damping: 12, stiffness: 200, mass: 0.6 },
        });

        const scale = Math.max(0, wordSpring);
        const opacity = Math.min(1, Math.max(0, (frame - wordDelay) / 3));

        return (
          <span
            key={index}
            style={{
              display: "inline-block",
              fontFamily: "'Impact', 'Inter', 'Montserrat', sans-serif",
              fontSize: isHighlighted ? 68 : 56,
              fontWeight: 900,
              letterSpacing: "1px",
              textTransform: "uppercase",
              transform: `scale(${scale})`,
              opacity,
              color: isHighlighted ? highlightColor : "#FFFFFF",
              textShadow: isHighlighted
                ? `0 0 25px ${highlightColor}88, 0 4px 10px rgba(0,0,0,0.9)`
                : "0 4px 12px rgba(0,0,0,0.85)",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
