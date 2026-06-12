"""Build a fully static listening page from listen/runs/<run>/*.wav.

Usage: python listen/build_page.py
Output: listen/index.html plus an .mp3 next to every .wav.

Players reference the MP3s with preload='none' and a baked-in duration
label: WAVs made the page fetch tens of MB of metadata up front, which is
what made it crawl on slow connections. Works opened locally and on any
static host (GitHub Pages, HF, etc.).
"""

import csv
import html
import json
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
SENTENCES = ROOT.parent / "data" / "eval" / "eval_sentences.csv"
SW_JUDGE = "Jacaranda-Health/ASR-STT"


def ensure_mp3(wav: Path) -> tuple[Path, float]:
    """Encode wav -> sibling mp3 if missing/stale; return (mp3, seconds)."""
    mp3 = wav.with_suffix(".mp3")
    info = sf.info(str(wav))
    if not mp3.exists() or mp3.stat().st_mtime < wav.stat().st_mtime:
        data, sr = sf.read(str(wav))
        sf.write(str(mp3), data, sr, format="MP3")
    return mp3, info.duration


def badge(wer):
    if wer is None:
        return ""
    color = "#2e7d32" if wer <= 0.2 else ("#e65100" if wer <= 1 else "#b71c1c")
    return f"<span class='badge' style='background:{color}'>WER {wer}</span>"


def main():
    with open(SENTENCES, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Dirs with a sentences.json are free-form demo sets (e.g. dia_long),
    # rendered in their own section instead of the eval grid.
    demo_dirs = sorted(d.name for d in RUNS.iterdir()
                       if d.is_dir() and (d / "sentences.json").exists())
    runs = sorted(d.name for d in RUNS.iterdir()
                  if d.is_dir() and any(d.glob("*.wav")) and d.name not in demo_dirs)
    wer = {}
    for run in runs:
        rj = RUNS / run / "results.json"
        if rj.exists():
            clips = json.loads(rj.read_text(encoding="utf-8"))["clips"]
            wer[run] = {cid: c.get(SW_JUDGE, {}).get("wer") for cid, c in clips.items()}

    body = ["<h1>Sauti TTS V2 — listening page</h1>"]
    ref_wav = ROOT / "reference" / "voice_prompt.wav"
    if ref_wav.exists():
        ref_mp3, ref_dur = ensure_mp3(ref_wav)
        body.append("<p class='note'>Reference voice (real WAXAL speaker, cloning prompt): "
                    f"<audio controls preload='none' src='reference/{ref_mp3.name}'></audio>"
                    f" <span class='dur'>{ref_dur:.1f}s</span></p>")
    body.append(f"<p>Runs: {', '.join(f'<b>{r}</b>' for r in runs)}. "
                "Badges show Swahili-judge WER (green ≤ 0.2, orange ≤ 1, red = run-on).</p>")

    current_cat = None
    for r in rows:
        if r["category"] != current_cat:
            current_cat = r["category"]
            body.append(f"<h2>{current_cat}</h2>")
        cid, text = r["id"], html.escape(r["text"])
        body.append(f"<div class='clip'><h3>{cid}</h3>"
                    f"<p class='text'>&ldquo;{text}&rdquo;</p><div class='grid'>")
        for run in runs:
            wav = RUNS / run / f"{cid}.wav"
            if wav.exists():
                mp3, dur = ensure_mp3(wav)
                b = badge(wer.get(run, {}).get(cid))
                body.append(f"<div><div class='lbl'>{run} {b} <span class='dur'>{dur:.1f}s</span></div>"
                            f"<audio controls preload='none' src='runs/{run}/{cid}.mp3'></audio></div>")
        body.append("</div></div>")

    for demo in demo_dirs:
        manifest = json.loads((RUNS / demo / "sentences.json").read_text(encoding="utf-8"))
        body.append(f"<h2>{demo} — long-form demos</h2>")
        for clip_id, meta in manifest.items():
            wav = RUNS / demo / f"{clip_id}.wav"
            if not wav.exists():
                continue
            mp3, dur = ensure_mp3(wav)
            cer = meta.get("check_cer")
            cer_note = f" · check-CER {cer}" if cer is not None else ""
            body.append(
                f"<div class='clip'><h3>{clip_id} <span class='dur'>"
                f"{meta.get('voice', '')} · {dur:.1f}s{cer_note}</span></h3>"
                f"<p class='text'>&ldquo;{html.escape(meta['text'])}&rdquo;</p>"
                f"<audio controls preload='none' src='runs/{demo}/{clip_id}.mp3'></audio></div>")

    page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Sauti TTS V2 — listening page</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 2rem auto; max-width: 1100px; color: #222; padding: 0 1rem; }}
h1 {{ border-bottom: 2px solid #444; padding-bottom: .3rem; }}
.text {{ color: #444; font-style: italic; margin: .2rem 0 .5rem; }}
.badge {{ color: #fff; border-radius: 4px; padding: 1px 7px; font-size: .75rem; font-style: normal; }}
.clip {{ border: 1px solid #ddd; border-radius: 8px; padding: .7rem 1rem; margin: .8rem 0; }}
.clip h3 {{ margin: 0; font-size: 1rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: .6rem; }}
.lbl {{ font-size: .82rem; font-weight: 600; margin-bottom: .2rem; }}
.note {{ background: #f5f5f5; border-left: 4px solid #888; padding: .6rem 1rem; }}
.dur {{ color: #777; font-weight: 400; font-size: .8rem; }}
audio {{ width: 250px; }}
</style></head><body>{''.join(body)}</body></html>"""

    out = ROOT / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(runs)} runs: {', '.join(runs)})")


if __name__ == "__main__":
    main()
