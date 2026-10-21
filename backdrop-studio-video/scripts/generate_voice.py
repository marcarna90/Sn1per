#!/usr/bin/env python3
"""Voix off de la composition `BackdropAd` (version calée sur la voix).

Source unique du script : src/synced/narration.json (champ `tts` = texte lu à voix haute).

Fonctionnement :
  1. une synthèse edge-tts par phrase (durée réelle mesurée avec ffprobe) → .cache/voice/<id>.mp3
  2. chaque phrase est placée à l'image près sur la timeline (même calcul que src/synced/timeline.ts)
     et assemblée en une seule piste → public/voiceover_synced.mp3
  3. src/synced/timeline.generated.json reçoit les durées : Remotion en déduit scènes, sous-titres et audio.

Si la durée estimée sort de `targetTotalSec` (35–45 s), le débit de la voix est réglé automatiquement
(+10 % → jusqu'à +20 %) et tout est re-synthétisé. Désactivable avec --no-fit.

Usage :
  python3 scripts/generate_voice.py
  python3 scripts/generate_voice.py --voice fr-FR-DeniseNeural --rate +10%
  python3 scripts/generate_voice.py --no-fit
  python3 scripts/generate_voice.py --proxy http://127.0.0.1:3128   # si besoin d'un proxy
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
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
NARRATION = ROOT / "src" / "synced" / "narration.json"
MANIFEST = ROOT / "src" / "synced" / "timeline.generated.json"
CACHE_DIR = ROOT / ".cache" / "voice"
PUBLIC_DIR = ROOT / "public"

# Doivent rester identiques à src/synced/timeline.ts
FPS = 30
LEAD_FRAMES = 6
LEAD_SEC = LEAD_FRAMES / FPS

RETRIES = 3
RATE_MIN, RATE_MAX = -10, 20  # bornes (en %) pour que la voix reste naturelle
MAX_FIT_PASSES = 2


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def probe_duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]))


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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    segments: dict[str, dict] = {}
    for seg in cfg["segments"]:
        dest = CACHE_DIR / f"{seg['id']}.mp3"
        await synthesize(seg["tts"], dest, voice, rate, pitch, proxy)
        duration = round(probe_duration(dest), 3)
        segments[seg["id"]] = {"durationSec": duration}
        print(f"  {seg['id']:<7} {duration:5.2f}s", flush=True)
    return segments


def slot_frames(cfg: dict, index: int, seg: dict, speech_sec: float) -> int:
    """Images réservées au segment : voix + respiration (ou plan final) + temps de lecture ajouté. Miroir de timeline.ts."""
    last = index == len(cfg["segments"]) - 1
    gap = round(cfg["gapSec"] * FPS)
    tail = round(cfg["tailSec"] * FPS)
    hold = round(seg.get("holdSec", 0) * FPS)
    return math.ceil(speech_sec * FPS) + (tail if last else gap) + hold


def overhead(cfg: dict) -> float:
    """Durée de la vidéo qui n'est pas de la parole : amorce, respirations, temps de lecture ajouté, plan final."""
    holds = sum(s.get("holdSec", 0) for s in cfg["segments"])
    return LEAD_SEC + cfg["gapSec"] * (len(cfg["segments"]) - 1) + holds + cfg["tailSec"]


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
    factor = speech / (goal - overhead(cfg))  # >1 : il faut accélérer
    new_pct = round(((1 + rate_pct / 100) * factor - 1) * 100)
    return max(RATE_MIN, min(RATE_MAX, new_pct))


def build_track(cfg: dict, segments: dict[str, dict], dest: Path) -> float:
    """Place chaque phrase à l'image près (même arithmétique que timeline.ts) et écrit une piste unique."""
    inputs: list[str] = []
    chains: list[str] = []
    expected_frames = LEAD_FRAMES
    for i, seg in enumerate(cfg["segments"]):
        frames = slot_frames(cfg, i, seg, segments[seg["id"]]["durationSec"])
        expected_frames += frames
        slot = frames / FPS + (LEAD_SEC if i == 0 else 0)
        delay = f"adelay={round(LEAD_SEC * 1000)}:all=1," if i == 0 else ""
        inputs += ["-i", str(CACHE_DIR / f"{seg['id']}.mp3")]
        chains.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,{delay}apad=whole_dur={slot:.4f},atrim=0:{slot:.4f}[a{i}]"
        )
    n = len(cfg["segments"])
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
         "-c:a", "libmp3lame", "-b:a", "160k", "-ar", "48000", "-ac", "1", str(dest)])
    duration = probe_duration(dest)
    expected = expected_frames / FPS
    if abs(duration - expected) > 0.15:
        print(f"⚠ piste de {duration:.2f}s au lieu de {expected:.2f}s attendues : vérifier le calage.", file=sys.stderr)
    return duration


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

    track_name = cfg["trackFile"]
    track_duration = build_track(cfg, segments, PUBLIC_DIR / track_name)

    MANIFEST.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "voice": args.voice,
                "rate": rate,
                "track": {"file": track_name, "durationSec": round(track_duration, 3)},
                "segments": segments,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nOK : public/{track_name} ({track_duration:.1f}s), manifeste src/synced/timeline.generated.json")
    print(f"Voix {args.voice} {rate} — vidéo estimée {total:.1f}s")
    if not lo <= total <= hi:
        print(f"⚠ Hors cible ({lo}-{hi}s) malgré le réglage : raccourcis un texte dans src/synced/narration.json.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
