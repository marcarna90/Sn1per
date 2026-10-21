import React from "react";
import { Root } from "./Root";
import { SyncedRoot } from "./synced/Root";

/**
 * Point d'entrée : enregistre les deux compositions.
 *  - BackdropStudioAd : la version "scènes à durées fixes" (src/Root.tsx, MainVideo)
 *  - BackdropAd       : la version calée sur la voix (src/synced/)
 */
export const Compositions: React.FC = () => (
  <>
    <Root />
    <SyncedRoot />
  </>
);
