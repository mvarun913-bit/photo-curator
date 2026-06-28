# Photo Curator

A fast, zero-cost first-pass cull for travel photos. Point it at a folder and it
sorts every image into four buckets using **technical checks only** — sharpness,
exposure, resolution, aspect ratio, and near-duplicate detection. No AI/vision
calls, so it costs nothing to run and is fast even on big folders.

Built for a faceless travel-photography workflow with 4:5 portrait slides, but
the thresholds are tunable for any style.

## Buckets

| Folder | What lands here |
|--------|-----------------|
| `instagram/` | Crisp **and** portrait/square — fits the 4:5 slide format |
| `keep/` | Technically fine, but landscape or just not standout |
| `review/` | Soft focus, off exposure, or a near-duplicate — needs your eye |
| `delete/` | Tiny images/screenshots, corrupt files, or exact duplicates |

## Safety

- **It never deletes anything.** Files are only *moved* into subfolders. The
  `delete/` folder is a holding pen you empty yourself.
- **Dry-run by default.** Running it with no flags only writes a report
  (`_curation_report.md`) and moves nothing. You have to pass `--apply` to sort.

---

## Install

You need Python 3 and a few imaging libraries (one time):

```bash
pip install -r requirements.txt
```
(or: `pip install pillow opencv-python-headless numpy pillow-heif`)

`pillow-heif` is optional — it lets the tool read iPhone `.heic` files.

### Option A — as a Claude Code plugin

If you use [Claude Code](https://docs.claude.com/en/docs/claude-code/overview),
install it as a skill so you can just say *"curate my photos in ~/Pictures/trip"*:

```
/plugin marketplace add mvarun913-bit/photo-curator
/plugin install photo-curator@photo-curator
/reload-plugins
```

Then in any session, ask it to curate a folder. It runs the dry pass, shows you
the report, and waits for your OK before sorting.

> If the marketplace add fails with an SSH error, clone over HTTPS instead:
> ```
> git clone https://github.com/mvarun913-bit/photo-curator.git ~/.claude/plugins/marketplaces/photo-curator
> ```
> then `/plugin marketplace add ~/.claude/plugins/marketplaces/photo-curator`.

### Option B — as a standalone script (no Claude Code needed)

Clone the repo and run it directly:

```bash
git clone https://github.com/mvarun913-bit/photo-curator.git
cd photo-curator

# Dry run — writes a report, moves nothing:
python3 skills/photo-curator/curate.py "/path/to/your/photos"

# Apply — actually sorts files into bucket subfolders:
python3 skills/photo-curator/curate.py "/path/to/your/photos" --apply
```

Add `--copy` to copy instead of move (leaves your originals in place).

---

## Tuning

This is a v1 metadata pass, so the cutoffs may need one calibration run on your
own camera's photos. If good shots land in `review/`, or junk slips into
`instagram/`, edit the constants at the top of `skills/photo-curator/curate.py`:

| Constant | Controls |
|----------|----------|
| `BLUR_SHARP` / `BLUR_SOFT` | The sharpness bar |
| `EXP_DARK` / `EXP_BRIGHT` / `CLIP_FRAC` | Exposure tolerance |
| `DUP_DISTANCE` | How aggressively near-duplicates are grouped |
| `PORTRAIT_MAX_AR` | What counts as 4:5-friendly |
| `MIN_MEGAPIXELS` / `MIN_LONG_EDGE` | The "too small / screenshot" cutoff |

## Known limits

- **No content judgment yet.** A sharp, well-exposed photo of a parking lot
  scores the same as a sharp landscape. Subject/composition is a future v2
  vision pass — the idea is to run this cheap pass first, then point real visual
  judgment only at the survivors.
- Shallow depth-of-field shots can read as "soft" and land in `review/` — which
  is exactly why soft images are never auto-deleted.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, share it.
