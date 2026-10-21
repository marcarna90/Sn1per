#!/usr/bin/env python3
"""Génère la voix off (edge-tts) et le manifeste de timing de la vidéo.

Source unique du script : src/narration.json (champ `tts` = texte lu à voix haute).
Sorties :
  - public/voice/<id>.mp3            un fichier par segment
  - src/timeline.generated.json      durée mesurée de chaque mp3 (lue par Remotion)

Remotion cale ensuite chaque scène sur ces durées : changer le texte ou la voix,
relancer ce script, puis re-rendre suffit à garder audio et image synchronisés.

Réglage automatique du débit : si la vidéo estimée sort de la fenêtre `targetTotalSec`
(35–45 s par défaut), le script recalcule le débit (`rate`) nécessaire et re-synthétise.
Désactivable avec --no-fit.

Usage :
  python3 scripts/generate_voice.py
  python3 scripts/generate_voice.py --voice fr-FR-DeniseNeural --rate +0%
  python3 scripts/generate_voice.py --no-fit
  python3 scripts/generate_voice.py --proxy http://127.0.0.1:3128   # si besoin d'un proxy
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import edge_tts
except ImportError:  # pragma: no cover
    sys.exit("edge-tts manquant : pip install edge-tts")

ROOT = Path(__file__).resolve().parent.parent
NARRATION = ROOT / "src" / "narration.json"
MANIFEST = ROOT / "src" / "timeline.generated.json"
OUT_DIR = ROOT / "public" / "voice"
RETRIES = 3
LEAD_SEC = 6 / 30  # LEAD_FRAMES / FPS dans src/timeline.ts
RATE_MIN, RATE_MAX = -10, 20  # bornes (en %) pour que la voix reste naturelle
MAX_FIT_PASSES = 2


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


async def synthesize(text: str, dest: Path, voice: str, rate: str, pitch: str, proxy: str | None) -> None:
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, proxy=proxy)
            await communicate.save(str(dest))
            if dest.stat().st_size == 0:
                raise RuntimeError("fichier audio vide")
            return
        except Exception as exc:  # noqa: BLE001 - on réessaie quelle que soit l'erreur réseau
            last = exc
            dest.unlink(missing_ok=True)
            if attempt < RETRIES:
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"échec de la synthèse après {RETRIES} essais : {last}")


async def synthesize_all(cfg: dict, voice: str, rate: str, pitch: str, proxy: str | None) -> dict[str, dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    segments: dict[str, dict] = {}
    for seg in cfg["segments"]:
        dest = OUT_DIR / f"{seg['id']}.mp3"
        await synthesize(seg["tts"], dest, voice, rate, pitch, proxy)
        duration = probe_duration(dest)
        segments[seg["id"]] = {"file": f"voice/{dest.name}", "durationSec": round(duration, 3)}
        print(f"  {seg['id']:<7} {duration:5.2f}s", flush=True)
    return segments


def overhead(cfg: dict) -> float:
    """Durée de la vidéo qui n'est pas de la parole : amorce, respirations entre segments, plan final."""
    return LEAD_SEC + cfg["gapSec"] * len(cfg["segments"]) + cfg["tailSec"]


def total_duration(cfg: dict, segments: dict[str, dict]) -> tuple[float, float]:
    speech = sum(s["durationSec"] for s in segments.values())
    return speech, speech + overhead(cfg)


def parse_rate(rate: str) -> int:
    m = re.fullmatch(r"([+-]?\d+)%", rate.strip())
    if not m:
        sys.exit(f"--rate invalide : {rate!r} (attendu : +5%, -3%, +0%…)")
    return int(m.group(1))


def refit_rate(cfg: dict, rate_pct: int, speech: float) -> int:
    """Débit (en %) qui ramène la vidéo au milieu-haut de la fenêtre cible."""
    lo, hi = cfg["targetTotalSec"]
    total = speech + overhead(cfg)
    goal = hi - 2 if total > hi else lo + 2
    wanted_speech = goal - overhead(cfg)
    factor = speech / wanted_speech  # >1 : il faut accélérer
    new_pct = round(((1 + rate_pct / 100) * factor - 1) * 100)
    return max(RATE_MIN, min(RATE_MAX, new_pct))


async def main() -> int:
    cfg = json.loads(NARRATION.read_text(encoding="utf-8"))

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--voice", default=cfg["voice"])
    parser.add_argument("--rate", default=cfg["rate"])
    parser.add_argument("--pitch", default=cfg["pitch"])
    parser.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"))
    parser.add_argument("--no-fit", action="store_true", help="ne pas ajuster le débit pour tenir dans la durée cible")
    args = parser.parse_args()

    lo, hi = cfg["targetTotalSec"]
    rate_pct = parse_rate(args.rate)

    for attempt in range(MAX_FIT_PASSES + 1):
        rate = f"{rate_pct:+d}%"
        print(f"→ synthèse {args.voice} {rate}", flush=True)
        segments = await synthesize_all(cfg, args.voice, rate, args.pitch, args.proxy)
        speech, total = total_duration(cfg, segments)
        print(f"  voix {speech:.1f}s · vidéo estimée {total:.1f}s (cible {lo}-{hi}s)", flush=True)

        if args.no_fit or lo <= total <= hi:
            break
        new_pct = refit_rate(cfg, rate_pct, speech)
        if new_pct == rate_pct or attempt == MAX_FIT_PASSES:
            break
        print(f"  hors cible → débit {rate_pct:+d}% → {new_pct:+d}%", flush=True)
        rate_pct = new_pct

    MANIFEST.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "voice": args.voice,
                "rate": rate,
                "segments": segments,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nOK : {len(segments)} fichiers dans public/voice/, manifeste src/timeline.generated.json")
    print(f"Voix {args.voice} {rate} — vidéo estimée {total:.1f}s")
    if not lo <= total <= hi:
        print(f"⚠ Hors cible ({lo}-{hi}s) malgré le réglage : raccourcis un texte dans src/narration.json.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
