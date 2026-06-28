#!/usr/bin/env python3
"""
farandframed photo curator - metadata pass (v1)

Triages a folder of trip photos into buckets using cheap, fast technical
checks ONLY (no AI vision, no token cost): sharpness, exposure, resolution,
aspect ratio, and near-duplicate detection.

Buckets:
  instagram/  technically excellent AND portrait/square (4:5-friendly)
  keep/       technically fine, but landscape or just not standout
  review/     soft focus, bad exposure, or a near-duplicate - needs your eye
  delete/     high-confidence junk: tiny images/screenshots, corrupt, exact dupes

SAFETY: nothing is ever deleted. Files are MOVED into subfolders, and only
when you pass --apply. Without --apply it just writes the report.
The delete/ folder is a holding pen you empty yourself.

Usage:
  python3 curate.py /path/to/photos            # dry run, writes report only
  python3 curate.py /path/to/photos --apply    # actually move files
  python3 curate.py /path/to/photos --apply --copy   # copy instead of move
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

import numpy as np
from PIL import Image
import cv2

# Optional HEIC/HEIF support (iPhone). Safe if not installed.
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC = True
except Exception:
    HEIC = False

# ---- tunable thresholds (defaults are conservative) ----
MIN_MEGAPIXELS = 1.0     # below this = likely screenshot/thumbnail -> delete
MIN_LONG_EDGE = 1000     # px; below this = too small to post -> delete
BLUR_SHARP = 120.0       # Laplacian variance above this = crisp
BLUR_SOFT = 35.0         # below this = clearly soft -> review (NOT delete; could be bokeh)
EXP_DARK = 38            # mean brightness below this = underexposed -> review
EXP_BRIGHT = 218         # mean brightness above this = overexposed -> review
CLIP_FRAC = 0.30         # fraction of pixels crushed/blown to flag exposure
PORTRAIT_MAX_AR = 1.05   # width/height at or below this = portrait/square (4:5-friendly)
DUP_DISTANCE = 6         # hamming distance on 64-bit dHash; <= is a near-duplicate

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
if HEIC:
    EXTS |= {".heic", ".heif"}

BUCKETS = ["instagram", "keep", "review", "delete"]


def dhash(gray, hash_size=8):
    """Difference hash -> 64-bit int. Pure numpy, no extra deps."""
    small = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def load_gray_and_meta(path):
    """Return (gray_array, width, height, camera) or raise."""
    img = Image.open(path)
    img.load()
    w, h = img.size
    camera = ""
    try:
        ex = img.getexif()
        make = (ex.get(271) or "").strip()
        model = (ex.get(272) or "").strip()
        camera = (make + " " + model).strip()
    except Exception:
        camera = ""
    rgb = img.convert("RGB")
    arr = np.asarray(rgb)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return gray, w, h, camera


def analyze(path):
    """Compute all cheap metrics for one image."""
    gray, w, h, camera = load_gray_and_meta(path)
    mp = (w * h) / 1_000_000.0
    long_edge = max(w, h)
    ar = w / h if h else 1.0

    # downscale for resolution-independent sharpness
    scale = 1024.0 / max(gray.shape)
    g = cv2.resize(gray, (0, 0), fx=scale, fy=scale) if scale < 1 else gray
    blur = float(cv2.Laplacian(g, cv2.CV_64F).var())

    mean_b = float(gray.mean())
    total = gray.size
    crushed = float((gray < 6).sum()) / total
    blown = float((gray > 250).sum()) / total

    return {
        "w": w, "h": h, "mp": mp, "long_edge": long_edge, "ar": ar,
        "blur": blur, "mean_b": mean_b, "crushed": crushed, "blown": blown,
        "camera": camera, "hash": dhash(gray),
    }


def classify(m, dup_role):
    """Return (bucket, reason). dup_role: 'unique' | 'dup-extra' | 'near-dup'."""
    if dup_role == "dup-extra":
        return "delete", "exact duplicate of another shot"
    if m["long_edge"] < MIN_LONG_EDGE or m["mp"] < MIN_MEGAPIXELS:
        return "delete", f"too small ({m['w']}x{m['h']}, {m['mp']:.1f}MP) - likely screenshot/thumbnail"
    if dup_role == "near-dup":
        return "review", "near-duplicate of a sharper shot - pick your favorite"
    if m["blur"] < BLUR_SOFT:
        return "review", f"looks soft (sharpness {m['blur']:.0f}) - check if intentional bokeh"
    if m["mean_b"] < EXP_DARK or m["crushed"] > CLIP_FRAC:
        return "review", f"underexposed (brightness {m['mean_b']:.0f})"
    if m["mean_b"] > EXP_BRIGHT or m["blown"] > CLIP_FRAC:
        return "review", f"overexposed (brightness {m['mean_b']:.0f}, {m['blown']*100:.0f}% blown)"

    sharp = m["blur"] >= BLUR_SHARP
    portrait = m["ar"] <= PORTRAIT_MAX_AR
    if sharp and portrait:
        return "instagram", f"crisp (sharpness {m['blur']:.0f}) + portrait/4:5-friendly (AR {m['ar']:.2f})"
    if not portrait:
        return "keep", f"good shot but landscape (AR {m['ar']:.2f}) - not your 4:5 slide format"
    return "keep", f"fine but not standout (sharpness {m['blur']:.0f})"


def main():
    ap = argparse.ArgumentParser(description="farandframed photo curator (metadata pass)")
    ap.add_argument("folder", help="folder of photos to triage")
    ap.add_argument("--apply", action="store_true", help="actually move files (default: report only)")
    ap.add_argument("--copy", action="store_true", help="copy instead of move (use with --apply)")
    args = ap.parse_args()

    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")

    files = [f for f in sorted(os.listdir(root))
             if os.path.splitext(f)[1].lower() in EXTS
             and os.path.isfile(os.path.join(root, f))]
    if not files:
        sys.exit(f"No images found in {root}")

    print(f"Scanning {len(files)} images in {root} ...")
    if not HEIC:
        print("  (note: HEIC/HEIF support off - run 'pip install pillow-heif' to include iPhone .heic files)")

    results = []
    for f in files:
        p = os.path.join(root, f)
        try:
            m = analyze(p)
            results.append({"file": f, "m": m, "err": None})
        except Exception as e:
            results.append({"file": f, "m": None, "err": str(e)})

    # ---- duplicate clustering on dHash ----
    ok = [r for r in results if r["m"]]
    roles = {r["file"]: "unique" for r in ok}
    used = set()
    for i, r in enumerate(ok):
        if r["file"] in used:
            continue
        group = [r]
        for r2 in ok[i + 1:]:
            if r2["file"] in used:
                continue
            if hamming(r["m"]["hash"], r2["m"]["hash"]) <= DUP_DISTANCE:
                group.append(r2)
                used.add(r2["file"])
        if len(group) > 1:
            # winner = sharpest in the group
            group.sort(key=lambda x: x["m"]["blur"], reverse=True)
            for loser in group[1:]:
                exact = hamming(group[0]["m"]["hash"], loser["m"]["hash"]) == 0
                roles[loser["file"]] = "dup-extra" if exact else "near-dup"

    # ---- classify ----
    plan = {b: [] for b in BUCKETS}
    for r in results:
        if r["err"]:
            plan["delete"].append((r["file"], f"could not open ({r['err']})", r))
            continue
        bucket, reason = classify(r["m"], roles[r["file"]])
        plan[bucket].append((r["file"], reason, r))

    # ---- apply moves ----
    moved = 0
    if args.apply:
        for b in BUCKETS:
            if plan[b]:
                os.makedirs(os.path.join(root, b), exist_ok=True)
        for b in BUCKETS:
            for fname, _, _ in plan[b]:
                src = os.path.join(root, fname)
                dst = os.path.join(root, b, fname)
                if os.path.exists(src):
                    (shutil.copy2 if args.copy else shutil.move)(src, dst)
                    moved += 1

    # ---- report ----
    lines = [f"# Photo curation report", "",
             f"**Folder:** `{root}`  ",
             f"**Run:** {datetime.now():%Y-%m-%d %H:%M}  ",
             f"**Mode:** {'APPLIED (files moved)' if args.apply else 'DRY RUN (no files moved)'}  ",
             f"**Images scanned:** {len(files)}", "",
             "> Metadata pass only - judged on sharpness, exposure, resolution, "
             "aspect ratio, and duplicates. No visual/content judgment yet. "
             "Nothing was deleted; `delete/` is a holding pen for you to empty.", ""]
    summary = " · ".join(f"{b}: {len(plan[b])}" for b in BUCKETS)
    lines += [f"**Tally —** {summary}", ""]
    titles = {
        "instagram": "Instagram-worthy",
        "keep": "Keep (good, B-roll or landscape)",
        "review": "Review (your eye needed)",
        "delete": "Delete candidates (holding pen)",
    }
    for b in BUCKETS:
        if not plan[b]:
            continue
        lines += [f"## {titles[b]} — {len(plan[b])}", "",
                  "| File | Why |", "|------|-----|"]
        for fname, reason, _ in plan[b]:
            lines.append(f"| `{fname}` | {reason} |")
        lines.append("")

    report_path = os.path.join(root, "_curation_report.md")
    with open(report_path, "w") as fh:
        fh.write("\n".join(lines))

    print(f"\n{summary}")
    print(f"Report: {report_path}")
    if not args.apply:
        print("Dry run - no files moved. Re-run with --apply to sort them.")
    else:
        print(f"Moved {moved} files into subfolders.")


if __name__ == "__main__":
    main()
