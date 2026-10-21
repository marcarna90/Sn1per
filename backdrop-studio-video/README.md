# BACKDROP STUDIO™ PRO — pub verticale 1080×1920

Pub TikTok / Reels / Shorts (9:16, 30 fps, ≈ 40 s) construite avec **Remotion** (React + TypeScript), des **vraies photos** (`public/images/`) et une voix off féminine **edge-tts**.
Boutique : <https://rontsr.mychariow.shop>

## Deux compositions

| | `BackdropStudioAd` | `BackdropAd` |
|---|---|---|
| Code | `src/Root.tsx`, `src/MainVideo.tsx`, `src/scenes/`, `src/components/KineticCaption.tsx` (version fournie) | `src/synced/` |
| Timing | scènes à durées fixes (6 / 12 / 12 / 10 s), sous-titres par plages d'images | scènes, sous-titres et audio **calés sur la durée réelle de chaque phrase** |
| Voix | `public/voiceover_femme.mp3`, un seul fichier : `npm run voice:femme` | `public/voiceover_synced.mp3`, assemblé image par image : `npm run voice` |
| Rendu | `npm run render` → `out/pub_backdrop.mp4` | `npm run render:synced` → `out/backdrop-studio-pro-ad.mp4` |

**Laquelle choisir avec la voix ?** `BackdropAd`. Avec le texte fourni, la voix annonce « Bloc 3 » vers 19 s alors que la carte du bloc 3 de
`BackdropStudioAd` apparaît à 12 s (`delay: 185`) : l'image et la voix ne se correspondent pas, car les durées sont fixées à la main.
`BackdropAd` mesure chaque phrase après synthèse et en déduit tout le reste.

## Pipeline

```bash
npm install
pip install edge-tts            # + ffmpeg/ffprobe installés sur la machine

# version calée sur la voix (recommandée)
npm run voice                   # voix + mesure des durées + piste unique
npm run render:synced

# version fournie
npm run voice:femme             # public/voiceover_femme.mp3 (+ public/subtitles.srt)
npm run render
```

`npm run studio` ouvre l'aperçu interactif. Sans fichier audio, les deux compositions se rendent en muet (utile pour travailler le visuel).

La voix est `fr-FR-VivienneMultilingualNeural` (meilleure avec les mots anglais comme « Identity Lock »), alternative `fr-FR-DeniseNeural`.
Le service de synthèse (`speech.platform.bing.com`) doit être joignable depuis la machine qui lance `npm run voice` / `voice:femme`.

### Comment `BackdropAd` reste synchronisé

1. `src/synced/narration.json` est la source unique : texte lu (`tts`), sous-titres (`caption`), voix, débit, pauses (`holdSec` = temps de lecture ajouté après une phrase).
2. `scripts/generate_voice.py` synthétise chaque phrase, mesure sa durée (`ffprobe`), la place à l'image près sur la timeline et écrit une piste unique + `src/synced/timeline.generated.json`.
3. `src/synced/timeline.ts` en déduit début et durée de chaque phrase, donc de chaque scène ; scènes, sous-titres et audio lisent la même timeline.
4. Si la durée estimée sort de **35–45 s**, le débit est réglé automatiquement (+10 % → jusqu'à +20 %) puis tout est re-synthétisé.

## Modifications apportées à la version fournie

Le code fourni a été écrit tel quel, puis ces ajouts minimaux ont été faits :

- **Audio protégé** (`MainVideo.tsx`) : sans `public/voiceover_femme.mp3`, Remotion s'arrêtait en erreur 404. La piste n'est montée que si le fichier existe.
- **Police** : sans `fontFamily`, le texte tombait en Times. `Inter` (embarquée dans `public/fonts`) est appliquée, et ajoutée à la pile de `KineticCaption` après `Impact`.
- **Vraies photos** ajoutées dans les espaces vides, sans toucher à la structure ni au texte : photo qui se dégrade (`DegradedPhoto`), bande de photos (`PhotoStrip`), carrousel (`PhotoCarousel`).
- `scripts/generate_voiceover.py` : le script de voix fourni, avec `boundary="WordBoundary"` (sans cela les sous-titres sortent vides avec edge-tts 7.x), le proxy de l'environnement et des chemins relatifs au projet.

## Structure

```
src/
  Root.tsx, MainVideo.tsx, scenes/, components/KineticCaption.tsx   version fournie
  synced/                                                           version calée sur la voix
  components/                  PhotoCard, PhotoStrip, PhotoCarousel, DegradedPhoto, FaceCrop, Icons
  images.ts, theme.ts, fonts.ts
scripts/ generate_voiceover.py · generate_voice.py · stills.mjs
public/  images/ (4 photos) · fonts/
```

`COMP=BackdropStudioAd node scripts/stills.mjs <dossier> <image> [<image> …]` rend des images clés pour contrôler le visuel.

## À vérifier avant de publier

- **Allégations.** La fiche Chariow décrit « BACKDROP STUDIO™ — MASTER COLLECTION » (269 concepts, 300 combinaisons). Elle ne mentionne ni « Moteur d'Assemblage en 3 blocs », ni « 130 décors », ni « 10 poses / 8 cadrages », ni la compatibilité ChatGPT Images & Gemini, ni « réécrits par des photographes ».
  Elle précise aussi que les résultats varient selon l'outil et la photo de référence : « 100 % » et « le tout premier système » sont des promesses fortes à justifier.
- **Prix.** Le badge `-33 %` et les prix (4 000 F CFA au lieu de 6 000) de `BackdropAd` viennent de la fiche Chariow (`src/theme.ts`, `BRAND`) ; la promo court jusqu'au 1er novembre 2026.
- **Filigrane.** `park.jpg` porte le logo de l'outil de génération en bas à droite : les cartes recadrent la photo pour le masquer.
- **Zones de sécurité.** Contenu clé entre y ≈ 110 et y ≈ 1480 : le bas de l'écran est recouvert par l'interface de TikTok/Reels.
