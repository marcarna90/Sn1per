import React from "react";
import { Audio, getStaticFiles, Sequence, staticFile } from "remotion";
import { ProblemScene } from "./scenes/ProblemScene";
import { ThreeBlocksScene } from "./scenes/ThreeBlocksScene";
import { ProofScene } from "./scenes/ProofScene";
import { CtaScene } from "./scenes/CtaScene";
import { loadFonts } from "./fonts";
import { FONT_BODY } from "./theme";

loadFonts();

// Le rendu échoue (404) si public/voiceover_femme.mp3 n'existe pas encore :
// on ne monte la piste audio que si le fichier est présent.
const HAS_VOICEOVER = getStaticFiles().some((f) => f.name === "voiceover_femme.mp3");

export const MainVideo: React.FC = () => {
  return (
    <div style={{ flex: 1, backgroundColor: "#000000", fontFamily: FONT_BODY }}>
      {/* Voix off féminine générée */}
      {HAS_VOICEOVER && <Audio src={staticFile("voiceover_femme.mp3")} volume={1.0} />}

      {/* Scène 1 : Problème (0 à 6s = 180 frames) */}
      <Sequence from={0} durationInFrames={180}>
        <ProblemScene />
      </Sequence>

      {/* Scène 2 : 3 Blocs (6 à 18s = 360 frames) */}
      <Sequence from={180} durationInFrames={360}>
        <ThreeBlocksScene />
      </Sequence>

      {/* Scène 3 : Preuve / Fonctionnalités (18 à 30s = 360 frames) */}
      <Sequence from={540} durationInFrames={360}>
        <ProofScene />
      </Sequence>

      {/* Scène 4 : Appel à l'action / Boutique (30 à 40s = 300 frames) */}
      <Sequence from={900} durationInFrames={300}>
        <CtaScene />
      </Sequence>
    </div>
  );
};
