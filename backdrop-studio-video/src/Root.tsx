import React from "react";
import { Composition } from "remotion";
import { MainVideo } from "./MainVideo";

export const Root: React.FC = () => {
  return (
    <Composition
      id="BackdropStudioAd"
      component={MainVideo}
      durationInFrames={1200}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
