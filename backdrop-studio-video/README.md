# BACKDROP STUDIO™ PRO — pub verticale 1080×1920

Pub TikTok / Reels / Shorts (9:16, 30 fps, ≈ 40 s) construite avec **Remotion** (React + TypeScript) et une voix off **edge-tts**.
Boutique : <https://rontsr.mychariow.shop>

## Pipeline en 3 commandes

```bash
npm install
pip install edge-tts            # + ffmpeg/ffprobe installés sur la machine

npm run voice                   # 1. voix off (mp3 par phrase) + mesure des durées
npm run render                  # 2. MP4 final → out/backdrop-studio-pro-ad.mp4
```

`npm run studio` ouvre l'aperçu interactif Remotion pour retoucher les scènes.

## Comment l'audio et l'image restent synchronisés

1. `src/narration.json` est la **source unique** du script : texte lu (`tts`), sous-titres (`caption`), voix, débit.
2. `scripts/generate_voice.py` synthétise un mp3 par segment (`public/voice/`), mesure sa durée réelle avec `ffprobe`
   et l'écrit dans `src/timeline.generated.json`.
3. `src/timeline.ts` en déduit le début et la durée de chaque segment, donc de chaque scène, et la durée totale de la vidéo.
   Les scènes, les sous-titres et les `<Html5Audio>` lisent tous cette même timeline.
4. Si la durée estimée sort de **35–45 s**, le script règle automatiquement le débit de la voix (`+4 %` → jusqu'à `+20 %`) et re-synthétise.

Changer un texte ou la voix : modifier `narration.json`, relancer `npm run voice`, puis `npm run render`.
Sans fichiers audio, la vidéo utilise les durées prévues (`fallbackSec`) et reste muette : pratique pour travailler le visuel.

Voix testables : `fr-FR-HenriNeural` (défaut), `fr-FR-DeniseNeural`
(`python3 scripts/generate_voice.py --voice fr-FR-DeniseNeural`).
Les mots anglais sont écrits phonétiquement dans `tts` (« Aïdentiti Lok Pro ») ; ajuste à l'oreille si besoin.

## Structure

```
src/
  narration.json          script, sous-titres, voix, débit
  timeline.ts             timeline calculée depuis les durées audio
  BackdropAd.tsx          composition : fond, scènes, sous-titres, audio
  scenes/                 ProblemScene · RevealScene (3 blocs) · ProofScene · CtaScene
  components/             Background, Captions (sous-titres cinétiques), Portrait, StudioShot, Icons
  theme.ts                couleurs, polices, infos de la boutique (prix promo, URL)
scripts/
  generate_voice.py       edge-tts → mp3 + manifeste de durées
  stills.mjs              rend des images clés pour contrôler le visuel
public/fonts, public/voice
```

## À savoir

- **Maquettes illustratives.** Les portraits sont des illustrations vectorielles (pas des photos générées).
  La vidéo l'indique à l'écran (« Visuels illustratifs ») en cohérence avec la fiche produit.
  Pour montrer de vrais résultats, remplace `StudioShot` par des `<Img src={staticFile('...')} />`.
- **Prix et promo.** Le badge `-33 %` et les prix (`4 000 F CFA` au lieu de `6 000 F CFA`) viennent de la fiche Chariow
  « BACKDROP STUDIO™ » ; ils sont dans `src/theme.ts` (`BRAND`). À mettre à jour si le prix change.
- **Zones de sécurité.** Contenu clé entre y ≈ 110 et y ≈ 1480 : le bas de l'écran est recouvert par l'interface de TikTok/Reels.
- **Navigateur.** `remotion.config.ts` utilise un Chromium local s'il en trouve un ; sinon Remotion télécharge le sien au premier rendu.
