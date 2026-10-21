#!/usr/bin/env python3
"""Voix off féminine en un seul fichier : public/voiceover_femme.mp3 (+ public/subtitles.srt).

C'est le script fourni, avec trois corrections :
  - `boundary="WordBoundary"` est demandé explicitement : sans cela, edge-tts 7.x n'envoie que des
    SentenceBoundary, le filtre `chunk["type"] == "WordBoundary"` ne correspond à rien et le fichier
    de sous-titres sort vide ;
  - le proxy HTTPS de l'environnement est pris en compte s'il existe ;
  - les chemins sont relatifs au projet (le script marche depuis n'importe quel dossier).

Ce fichier alimente la composition `BackdropStudioAd` (<Audio src={staticFile("voiceover_femme.mp3")} />).
Pour la version calée sur la voix (`BackdropAd`), utiliser `npm run voice` à la place.

Usage : python3 scripts/generate_voiceover.py
"""
import asyncio
import os
import sys
from pathlib import Path

import edge_tts

# Choix de la voix féminine
VOICE = "fr-FR-VivienneMultilingualNeural"  # ou "fr-FR-DeniseNeural"

# Texte de la voix off pour votre pub
TEXT = (
    "Arrêtez de ruiner vos portraits avec l'intelligence artificielle ! "
    "Vous en avez marre des visages en plastique méconnaissables ? "
    "Voici Backdrop Studio Pro : le tout premier système en 3 blocs. "
    "Bloc 1 : Identity Lock, qui verrouille vos vrais traits et votre carnation. "
    "Bloc 2 : 130 décors réécrits par des photographes de studio. "
    "Bloc 3 : Un rendu physique professionnel avec éclairage studio réel. "
    "Fini les visages déformés. Obtenez vos portraits de luxe dès aujourd'hui. "
    "Téléchargez le pack sur notre boutique : rontsr.mychariow.shop !"
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "public" / "voiceover_femme.mp3"
SUBTITLE_FILE = ROOT / "public" / "subtitles.srt"


async def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # +10% de vitesse pour garder un rythme TikTok/Reels percutant
    communicate = edge_tts.Communicate(
        TEXT,
        VOICE,
        rate="+10%",
        boundary="WordBoundary",
        proxy=os.environ.get("HTTPS_PROXY"),
    )

    # Génération du fichier audio et des sous-titres
    sub_maker = edge_tts.SubMaker()
    with open(OUTPUT_FILE, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                sub_maker.feed(chunk)

    if OUTPUT_FILE.stat().st_size == 0:
        OUTPUT_FILE.unlink()
        print("❌ Aucun audio reçu.", file=sys.stderr)
        return 1

    SUBTITLE_FILE.write_text(sub_maker.get_srt(), encoding="utf-8")

    print(f"✅ Fichier audio généré : {OUTPUT_FILE}")
    if sub_maker.cues:
        print(f"✅ Fichier sous-titres généré : {SUBTITLE_FILE} ({len(sub_maker.cues)} repères)")
    else:
        print("⚠ Aucun repère de sous-titres reçu du service : le fichier .srt est vide (la vidéo n'en dépend pas).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
