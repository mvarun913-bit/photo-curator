---
name: photo-curator
description: "Triage a folder of trip/travel photos into instagram / keep / review / delete buckets using fast technical checks (sharpness, exposure, resolution, aspect ratio, duplicates) with NO AI vision cost. Use whenever the user wants to cull, sort, curate, or clean up a folder of photos, decide which shots are Instagram-worthy, find blurry or duplicate images, or prep a photo batch for posting. Tuned for a faceless travel-photography aesthetic with 4:5 portrait slides. Always dry-run first; never deletes files."
---

# Photo Curator (metadata pass, v1)

A fast, zero-token first-pass cull for trip photos. It judges each image on
**technical quality only** — sharpness, exposure, resolution, aspect ratio,
and near-duplicates — and sorts them into four buckets. It does **not** look at
content/subject yet (that's a future v2 vision pass).

## When to use
The user points at a folder of photos and wants them culled, sorted, or rated:
"curate my Utah photos", "which of these are postable", "find the blurry/duplicate
ones", "clean up this folder before I edit". Default target is a faceless travel
look: sharp, well-exposed, portrait/square (4:5-friendly).

## Buckets
- `instagram/` — crisp AND portrait/square (fits the 4:5 slide format)
- `keep/` — technically fine, but landscape or just not standout
- `review/` — soft focus, off exposure, or a near-duplicate — needs the user's eye
- `delete/` — high-confidence junk: tiny images/screenshots, corrupt files, exact duplicates

## Safety rules (do not violate)
1. **Never delete.** The script only ever MOVES files; `delete/` is a holding pen the user empties themselves.
2. **Dry-run first, always.** Run with no flags first and show the user the report. Only run `--apply` after they confirm.
3. If the user asks to "delete the bad ones," still route to `delete/` and tell them to empty it themselves after a glance.

## How to run

The `curate.py` script is bundled in this same skill directory. One-time
dependency setup (only needed once per machine):
```
pip install pillow opencv-python-headless numpy pillow-heif --break-system-packages
```
(`pillow-heif` is optional but needed to include iPhone `.heic` files.)

Step 1 — dry run (writes `_curation_report.md`, moves nothing). Run the
`curate.py` that sits next to this SKILL.md, passing the user's folder:
```
python3 <this-skill-dir>/curate.py "/path/to/photo/folder"
```
Read the report back to the user, summarize the tally, and ask if they want to apply it.

Step 2 — apply (only after the user confirms):
```
python3 <this-skill-dir>/curate.py "/path/to/photo/folder" --apply
```
Add `--copy` instead of moving if the user wants originals left in place.

## Calibrating the thresholds
This is a v1 metadata pass, so the sharpness/exposure cutoffs may need one tuning
run against the user's real photos and camera. If too many good shots land in
`review/`, or junk slips into `instagram/`, edit the threshold constants at the
top of `curate.py`:
- `BLUR_SHARP` / `BLUR_SOFT` — raise/lower the sharpness bar
- `EXP_DARK` / `EXP_BRIGHT` / `CLIP_FRAC` — exposure tolerance
- `DUP_DISTANCE` — how aggressively near-duplicates are grouped
- `PORTRAIT_MAX_AR` — what counts as 4:5-friendly

After the first real run, offer to adjust these based on what the user thinks
the script got wrong.

## Known limits (be honest about these)
- No content judgment yet — a sharp, well-exposed photo of a trash can scores
  the same as a sharp landscape. Subject/composition is the v2 vision pass.
- Shallow depth-of-field shots can read as "soft" and land in `review/` — that's
  why soft images are never auto-deleted.
- Sharpness is resolution-normalized but still varies by content; treat the
  buckets as a strong first sort, not a final verdict.
