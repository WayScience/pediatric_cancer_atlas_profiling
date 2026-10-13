---
name: cpg-pilot-data-organizer
description: Reorganizes raw Cell Painting microscope output (Opera Phenix/Harmony plate folders) into the exact directory structure the Broad Cell Painting Gallery (CPG) requires before upload, and generates the accompanying load_data.csv files. Use this whenever the user is preparing images/data for a Cell Painting Gallery deposit, mentions cpg0041-pccma, alexslemonade, pediatric cancer Cell Painting pilot data, "Round 1/2/3/4 pilot" imaging, SK-N-AS or CHP-134 screen plates, or asks to rename/restructure plate folders, build a load_data_csv, or validate a dataset structure before handing it off to CPG maintainers for upload to their staging bucket. Also use it if the user asks generally about Cell Painting Gallery folder structure, naming rules (batch/plate/source/project ids), or the "no double nesting" rule, even without a specific reorganization task.
---

# CPG pilot data organizer

Reorganizes raw plate-imaging output into the folder structure the Cell
Painting Gallery (CPG) requires, and generates the `load_data.csv` files
CPG needs alongside the images. Built around the `cpg0041-pccma`
(alexslemonade / Way Lab pediatric cancer) deposit, but the manifest-driven
approach generalizes to any arrayed Cell Painting dataset going into CPG.

**Read `references/cpg_data_structure.md` first** if you (the model using
this skill) aren't already familiar with the CPG directory structure rules —
project/source/batch/plate hierarchy, the full-plate-name vs plate-name
distinction, and the "no double nesting" rule. Everything in this skill's
scripts exists to enforce those rules mechanically rather than leave them as
things a person has to remember.

**Also read `references/pccma_project_notes.md`** if the task involves
cpg0041-pccma specifically — it has the fixed project/source ids, the
approved batch-folder names from the maintainer discussion, and the
important gotcha that Round 1 pilot data is *not* labeled "Round 1"
anywhere on disk (it's under the identifier `SN0313537`).

## Why a manifest instead of pattern-matching folder names

Don't try to infer rounds/plates/cell-lines by guessing at the raw folder
naming convention on the user's disk or server — it's inconsistent by
nature (that's the whole reason Round 1 ended up filed under `SN0313537`
instead of anything with "round" in it). Instead, always build an explicit
manifest (YAML or JSON) that states, for each target batch, exactly which
raw folder it comes from. This is slower up front but means nothing gets
silently mis-filed or skipped.

Start from `assets/manifest.example.yaml`, which is pre-filled with the
batch names already agreed on for cpg0041-pccma (Round2/3/4, SK-N-AS,
CHP-134) and a placeholder entry for the Round1/SN0313537 case. Copy it,
then work with the user to fill in real `raw_source` paths — ask them where
each round's raw data actually lives (local disk, a connected drive, an HPC
path) rather than guessing.

**Don't make the user hand-type every plate/cell-line/variant combination.**
Real pccma raw data has a LOT of them (a single round can have a dozen+
"Plate N <CellLine> Reimage" folders). Use `scripts/scan_raw_data.py` to
auto-generate manifest entries from the raw folder names instead — see
"Auto-generating manifest entries" below. Always show the user the scanned
output before merging it into the real manifest; the parser is pattern-based
and can occasionally hit a folder name it doesn't recognize (it prints those
to stderr rather than silently skipping them).

## Auto-generating manifest entries

`scripts/scan_raw_data.py` recognizes two raw-folder naming conventions
found in the real pccma data and turns them into manifest YAML fragments:

- **Round 2/3/4 style**: folders directly under a round's raw directory
  named `Plate <N> All Cell Lines` (the original full-plate scan) or
  `Plate <N> <CellLine> Reimage` (a targeted re-image). Each of these
  folders can itself contain multiple plate-barcode subfolders — every
  barcode becomes its own plate entry in the batch.
- **Round 1 style** (the `SN0313537` folder): bare barcode folders directly
  under it are the original plates; folders named `YYYYMMDD_<CellLine>_Re-imaged`
  are dated targeted re-images (Round 1 didn't use "Plate N" labels), and
  these also wrap barcode subfolders one level down.

```
python scripts/scan_raw_data.py --raw-dir "/path/to/Round_2_data" --round-label Round2 --out round2.yaml
python scripts/scan_raw_data.py --raw-dir "/path/to/SN0313537" --round-label Round1 --out round1.yaml
```

The script auto-detects which style it's looking at from the folder names
present. Review the generated YAML with the user (it includes a `_comment`
line per batch naming which raw folder it came from and the cell-line name
as-found, before sanitizing), then merge the batches into the real manifest.

If a round's raw folder doesn't match either convention, the script exits
with the folder names it saw rather than guessing — don't try to force a
match by hand-editing the regexes to fit one dataset; ask the user what the
naming means instead.

**A real gotcha this surfaced**: plate barcodes get reused when a plate is
re-imaged later (same barcode, new acquisition timestamp) — e.g. barcode
`BR00145439` can legitimately appear both in a plate's original
`...AllCellLines`-derived batch and again in a later `..._Reimage` batch.
`reorganize.py` and `validate_structure.py` both know this is normal: they
only hard-fail on a plate-name collision *within* the same batch (a real
bug), and just print an informational note when the same plate-name shows
up across different batches.

## Workflow

1. **Build/update the manifest** with the user, one batch at a time — or
   use `scan_raw_data.py` (above) to generate most of it automatically. For
   any batch you still add by hand,
   each batch, confirm: which raw folder is the source, what round/plate
   label and cell line it is (or pass an explicit `batch_name` if the round
   concept doesn't apply, e.g. for the screen batches), and any variant
   suffix (`Reimage`, `Screen_Original`, `RowO_Repeat`, `Reupload`, etc.).

2. **Dry run the reorganization** (this is the default — nothing is copied
   yet):
   ```
   python scripts/reorganize.py manifest.yaml --target ./local_cpg_mirror
   ```
   This prints the planned mapping from each raw source to its target path
   under `<target>/<project_id>/<source_id>/images/<batch_name>/images/<full-plate-name>/`,
   and flags problems (missing raw sources, duplicate derived plate names)
   *before* anything is executed. Walk the user through this output and get
   their sign-off — these are irreplaceable microscopy images, so don't
   skip straight to `--execute`.

3. **Execute** once the dry run looks right:
   ```
   python scripts/reorganize.py manifest.yaml --target ./local_cpg_mirror --execute
   ```
   This copies files by default (originals untouched). **If `--target` is on
   the same drive as the raw data and free space is tight** (true for
   pccma's 18TB drive — it's already ~98% full), use `--hardlink` instead:
   it builds the whole CPG-structured tree with new directory entries
   pointing at the same underlying data, at zero extra disk cost, rather
   than duplicating potentially hundreds of GB per round. Hardlinks only
   work within one filesystem — the script fails clearly (not silently) if
   `--target` turns out to be on a different drive. Only add `--move`
   instead if the user explicitly confirms they have the raw data backed up
   elsewhere or don't need to keep a separate copy; `--move` and
   `--hardlink` are mutually exclusive.

   **Pass `--emit-batch-map <path.json>` on the dry run** (works without
   `--execute` — it's derived purely from the manifest). This writes
   `{plate_name: [batch_name, ...]}` for every plate whose images live in
   more than one batch — the exact input step 5's illum relocation needs.
   Don't hand-derive this mapping yourself by reading the manifest and
   transcribing which reimage batches contain which barcode (that's how the
   original Round 1 version of this went wrong — see
   `references/pccma_project_notes.md`); `reorganize.py` already computes it
   to print its own "NOTE: plate-name reused across batches" lines, so let
   it be the single source of truth.

4. **Generate load_data.csv for each plate.** For this project, **don't use
   `generate_load_data_csv.py` as the primary generator** — the real pipeline
   already has a better one: `pe2loaddata` + `1.illumination_correction/config_files/config.yml`,
   which maps channels by **name** (from Harmony's Index.idx.xml metadata),
   not by the numeric channel ID `generate_load_data_csv.py` uses. Channel-ID
   assignment isn't stable across imaging sessions, so the numeric approach
   is the wrong tool here — see `references/pccma_project_notes.md` for the
   full writeup, including why the existing reimage-merge logic in
   `0.create_loaddata_csvs.py` (one `<barcode>_concatenated.csv` per
   analyzed plate, folding reimaged wells into the original barcode and
   dropping the poor-quality original rows they replace) is correct and has
   been checked against the real Round 1 output.

   Once you have a `<barcode>_concatenated.csv` (or equivalent pe2loaddata
   output) for an analyzed plate, use `scripts/relocate_load_data_csv.py` to
   turn it into the CPG-structured `load_data.csv`:
   ```
   python scripts/relocate_load_data_csv.py \
     --manifest manifest.yaml \
     --csv "/path/to/1.illumination_correction/loaddata_csvs/Round_1_data/BR00143976_concatenated.csv" \
     --batch-name Round1 --plate-name BR00143976 \
     --target ./local_cpg_mirror \
     --out ./local_cpg_mirror/cpg0041-pccma/alexslemonade/workspace/load_data_csv/Round1/BR00143976/load_data.csv
   ```
   This reads each row's existing local `PathName_<Channel>`/`FileName_<Channel>`
   columns, matches that local path against the SAME manifest used for
   `reorganize.py`, and adds a `URL_<Channel>` column pointing at the eventual
   production `s3://cellpainting-gallery/...` path -- per row, not per file,
   because a merged plate's rows can legitimately point at images in several
   different CPG batch folders at once (its own original batch plus however
   many reimage batches contributed wells). `--batch-name` is the batch that
   "owns" this plate's workspace entry -- for a plate with merged reimaged
   wells, that's the **original** batch (e.g. `Round1`, not
   `Round1_A673_Reimage`), matching where its illum/profiles go in the next
   step. If any row's path doesn't match a raw_source in the manifest, the
   script refuses to write anything rather than emit a load_data_csv with
   broken URLs -- fix the manifest or double check you're using the CSV that
   matches it, don't force past this.

   `generate_load_data_csv.py` (numeric `--channel-map N=NAME`) is kept only
   as a fallback for a dataset with no Harmony XML metadata / pe2loaddata
   setup at all -- don't reach for it here. If you do need it elsewhere and
   the raw filenames aren't Opera Phenix/Harmony style (`r01c01f01p01-ch1...`),
   adjust `OPERA_PHENIX_FILENAME_RE` / `parse_opera_phenix_filename()` in
   `scripts/cpg_lib.py` -- that's the one place the pattern lives.

5. **Relocate illum and profiles outputs, for plates that were actually analyzed.**

   `illum` goes to `images/<batch>/illum/<plate>/` (confirmed against
   `data_structure.html`'s own example and discussion #98 — a per-PLATE
   subfolder inside `illum/`, not files sitting flat). It needs **multiple
   `--batch-name` values** whenever a plate's images live in more than one
   batch — the normal case for a reimaged plate (one batch for the original
   scan, one per targeted reimage): the same illum files get placed under
   every one of those batches' `illum/<plate>/`, since illum travels with a
   batch's images. CPG's docs don't explicitly cover this multi-batch case —
   this is a judgment call, flag it for the maintainers rather than treating
   it as settled.

   `profiles` goes to `workspace/profiles/<batch>/<plate>/`, with exactly
   ONE `--batch-name` — the plate's original/analysis-identity batch, never
   a reimage batch, since the analysis is one merged result regardless of
   which raw folders contributed images to it. It needs **multiple
   `--source-dir` values** to pull bulk (pycytominer, well-level) and
   single-cell profiles together — in this project these live across FOUR
   sibling directories: `bulk_profiles/`, `converted_profiles/`,
   `cleaned_profiles/` (CytoTable `_converted`/`_cleaned`), and
   `single_cell_profiles/` (`_sc_annotated`/`_sc_normalized`/`_sc_feature_selected`
   — the single-cell-granularity mirror of the bulk pipeline; easy to miss
   since its files aren't named "single_cell" and it's not nested under the
   other three — see `references/pccma_project_notes.md`). Filenames are
   kept as-is, not renamed to CPG's documented `.csv.gz` convention, and
   single-cell parquet has NO documented CPG location at all (`backend/` is
   SQLITE-only per the docs) — both are placeholders pending the CPG
   maintainers' confirmation.

   **Don't hand-type which batches each plate's illum needs.** Use
   `scripts/relocate_illum_and_profiles.py`, driven by the `--emit-batch-map`
   JSON from step 3 — it loops every plate in the map, calls
   `organize_workspace.py illum` with that plate's full batch list and
   `organize_workspace.py profiles` with just the base batch
   (alphabetically-first in the map — always the base batch, since
   `build_batch_name()` appends cell_line/variant AFTER round+plate, making
   the base name a strict prefix of every reimage variant), and keeps going
   past a single plate's failure (e.g. outputs not generated yet) rather
   than aborting the whole round:
   ```
   python scripts/relocate_illum_and_profiles.py \
     --batch-map /tmp/round2_batch_map.json \
     --illum-source-dir "<round's illum_directory/Round_N_data>" \
     --profile-source-dir "<round's bulk_profiles/Round_N_data>" \
     --profile-source-dir "<round's converted_profiles/Round_N_data>" \
     --profile-source-dir "<round's cleaned_profiles/Round_N_data>" \
     --profile-source-dir "<round's single_cell_profiles/Round_N_data>" \
     --target ./local_cpg_mirror --project-id cpg0041-pccma --source-id alexslemonade \
     --execute --hardlink
   ```
   `--emit-batch-map` includes every plate, reimaged or not — a plate never
   reimaged just gets a single-element batch list, so `relocate_illum_and_profiles.py`
   handles it with no special casing needed.

   **`cpg_pilot_transfer.sh` (repo root) is the one-command way to do all of
   the above, for all four rounds, in one run** — it loops rounds 1-4, and
   for each one runs `reorganize.py --emit-batch-map` (dry run), `reorganize.py
   --execute --hardlink` (images), `relocate_illum_and_profiles.py --execute
   --hardlink` (illum + all four profile source dirs), then prints (not runs)
   the exact `relocate_load_data_csv.py` command for every plate. Every step
   is rerun-safe, so running it again after a partial run — or after Round 1
   was already placed by an earlier, different method — just skips what's
   already correctly there instead of erroring; verified against a sandbox
   simulating exactly that (a plain-copy Round 1 illum file from an earlier
   bridge transfer, re-run through the hardlink path). `relocate_round1_illum_and_profiles.sh`
   and `relocate_rounds_2_3_4.sh` are its Round-1-only and Round-2-4-only
   predecessors, kept for reference/history — prefer `cpg_pilot_transfer.sh`
   going forward.

   **Use `--hardlink` for both, always**, once past a dry run against real
   data. It's essential for profiles: single-cell parquet files in this
   project run 1-13GB EACH (Round 1 alone is ~220GB of single-cell-scale
   parquet across its 6 barcodes), and copying (rather than hardlinking)
   even one round's worth would burn through the 18tbdrive's free space
   fast.

   `backend/` and `analysis/` (CellProfiler's sqlite + per-site CSV output)
   are NOT handled by this skill yet — the internal shape of the pipeline's
   `sqlite_outputs/` folder hasn't been confirmed closely enough to relocate
   correctly (a plain listing of one plate's worth is too large to safely
   infer from). Ask the user how it's laid out before extending
   `organize_workspace.py` to cover it.

6. **Metadata** (`workspace/metadata/platemaps/<batch>/`) — one of CPG's
   three mandatory pieces (images, load_data_csv, metadata) alongside step 5,
   easy to miss since `validate_structure.py` only started checking for it
   after the rest of the pipeline was already built. Unlike images/illum/
   profiles this is small (a few KB per batch, not GB), so it's built and
   pushed directly rather than left as a script for the user to run:
   ```
   python scripts/relocate_metadata.py \
     --batch-map /tmp/round1_batch_map.json \
     --barcode-platemap-csv "<project>/0.download_data/metadata/platemaps/Barcode_platemap_pilot_data.csv" \
     --platemap-source-dir "<project>/0.download_data/metadata/platemaps" \
     --target ./local_cpg_mirror --project-id cpg0041-pccma --source-id alexslemonade \
     --execute
   ```
   Transforms this project's raw records (`Barcode_platemap_pilot_data.csv`:
   barcode -> which plate-design CSV; `Assay_Plate<N>_platemap.csv`: one row
   per well) into CPG's documented shape (confirmed against
   [data_structure.html](https://broadinstitute.github.io/cellpainting-gallery/data_structure.html)
   2026-08-28): comma-separated `barcode_platemap.csv` with
   `Assay_Plate_Barcode`/`Plate_Map_Name` columns, and tab-separated
   `platemap/<Plate_Map_Name>.txt` with `plate_map_name`/`well_position` (CPG's
   required two) plus `cell_line`/`row`/`column`/`seeding_density`/`condition`.
   Lives only in the base batch (`batches[0]`, same convention as profiles) —
   a plate's physical design doesn't change on reimaging. For cpg0041-pccma
   specifically there are 13 platemap designs across 12 batches, because
   Round 1's single `Round1` batch covers TWO plate designs (Assay_Plate1 and
   Assay_Plate2) split across its 6 barcodes — confirmed against the barcode
   CSV, not assumed; every other batch is a clean 3-barcodes-to-1-platemap.
   **`time_point`** (24h/48h/72h per barcode, present in the raw barcode CSV)
   has no slot in CPG's schema and is dropped rather than silently reshaped —
   flag for Erin/Shantanu whether it belongs somewhere else. Rerun-safe like
   the rest of the pipeline, but treats a content mismatch as a hard stop
   rather than a silent skip, since these are hand-curated plate records, not
   regenerable data.

7. **Validate before handoff**:
   ```
   python scripts/validate_structure.py ./local_cpg_mirror/cpg0041-pccma
   ```
   (Or whatever local path holds the `<project_id>/` folder.) This checks
   folder-name character rules, the full-plate-name/plate-name relationship,
   presence of `load_data_csv/` and `metadata/`, and flags anything that
   looks like it might trip the maintainers' manual review. Fix every FAIL
   before telling the user it's ready to send to the CPG maintainers'
   staging bucket.

8. **Upload to CPG's staging bucket**, once `validate_structure.py` is clean.
   This part is deliberately NOT public documentation — CPG hands out
   per-prefix credentials individually (see
   [uploading_to_cpg.html](https://broadinstitute.github.io/cellpainting-gallery/uploading_to_cpg.html),
   confirmed 2026-08-28):
   1. Email Erin Weisbart / Shantanu Singh (already the contacts for
      cpg0041-pccma's discussion #98) for credentials scoped to your
      prefix, if you don't already have them.
   2. Generate a short-lived (12h) read/write token for your prefix:
      ```
      aws s3control get-data-access \
        --account-id 309624411020 \
        --target "s3://staging-cellpainting-gallery/cpg0041-pccma/*" \
        --permission READWRITE --duration-seconds 43200 --region us-east-1
      ```
      then export the `AccessKeyId`/`SecretAccessKey`/`SessionToken` from its
      output as `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`.
   3. Sync the local mirror up — this is the "easy" part, since the local
      tree built by this skill already matches the final structure exactly:
      ```
      aws s3 sync ./local_cpg_mirror/cpg0041-pccma s3://staging-cellpainting-gallery/cpg0041-pccma/ --region us-east-1
      ```
      `--region us-east-1` is mandatory (required for the Access Grants
      mechanism this uses). `sync` is resumable and skips files already
      uploaded, so if the 12h token expires partway through a multi-TB
      round, just regenerate a token and re-run the same command.
   4. Verify counts match (`find ... | wc -l` locally vs.
      `aws s3 ls ... --recursive | wc -l` on the bucket), then notify the
      maintainers to review/approve the move from staging to public.

   **Never run or draft this with real AWS credentials in this conversation**
   — treat the credential-generation and sync steps as something the user
   runs themselves, in their own terminal, exactly like the large-file
   `--hardlink` relocations above.

## Things worth double-checking with the user, every time

- Is the source id right? For cpg0041-pccma it's `alexslemonade`, not
  `broad` — an easy mistake since the imaging happened on Broad's Opera
  Phenix.
- Does every round the user mentions actually have a manifest entry? Round 1
  is easy to miss because it's filed under `SN0313537`.
- Are copies being made (not destructive moves) unless the user has
  explicitly confirmed otherwise?
- Has the user actually supplied the channel→stain mapping for
  load_data_csv, rather than the model guessing based on typical Cell
  Painting channel order?

## Files in this skill

- `scripts/cpg_lib.py` — shared name-sanitizing/batch-naming/filename-parsing
  logic (import this from the other scripts; don't reimplement it inline).
- `scripts/scan_raw_data.py` — auto-generates manifest batch/plate entries by
  parsing real raw-folder naming conventions (see "Auto-generating manifest
  entries" above) instead of requiring hand-typed entries for every
  plate/cell-line/variant combination.
- `scripts/reorganize.py` — manifest-driven dry-run/execute reorganizer.
- `scripts/generate_load_data_csv.py` — per-plate load_data.csv generator
  from raw filenames + numeric channel IDs. Fallback only -- see workflow
  step 4 for why this project uses `relocate_load_data_csv.py` instead.
- `scripts/relocate_load_data_csv.py` — turns a pe2loaddata-generated
  LoadData CSV (channel-NAME based, already merged across reimages by
  `0.create_loaddata_csvs.py`) into a CPG-structured load_data.csv, by
  matching each row's local path against the manifest and adding
  `URL_<Channel>` columns. Tested against all 6 real Round 1 barcodes.
- `scripts/organize_workspace.py` — relocates existing illum/profiles
  pipeline outputs into the CPG workspace structure (backend/analysis not
  yet handled — see the workflow step above). Supports multiple
  `--batch-name` (illum, for a plate reimaged into several batches),
  multiple `--source-dir` (profiles, for bulk + single-cell across all four
  sibling directories), and `--hardlink`. Rerun-safe: an existing
  destination file that's already the same hardlink, or same size (e.g.
  placed by an earlier non-hardlink run), is skipped rather than erroring;
  only a genuine size mismatch stops it. Tested against the real filename
  patterns (`<plate>_Illum<Channel>.npy`, `<plate>_bulk*.parquet`,
  `<plate>_converted.parquet`, `<plate>_cleaned.parquet`,
  `<plate>_sc_annotated/normalized/feature_selected.parquet`).
- `scripts/relocate_illum_and_profiles.py` — round-agnostic driver: reads a
  `reorganize.py --emit-batch-map` JSON and calls `organize_workspace.py`
  illum + profiles for every plate in it, with the right `--batch-name`(s)
  worked out automatically. This is the preferred way to run step 5 for any
  round (Round 1 included) — see the workflow step above.
- `cpg_pilot_transfer.sh` — **the recommended one-command entry point.**
  Loops all four rounds (1-4), running the full images -> illum+profiles ->
  load_data_csv-command-printing pipeline for each (see workflow step 5
  above for the exact steps). Includes Round 1 even though it was already
  reorganized earlier — every step is rerun-safe, so it just skips what's
  already correctly in place. Verified end-to-end against a sandbox
  (cold run across 2 rounds, a full rerun, and a rerun simulating Round 1's
  real on-disk state — an illum file placed as a plain copy by an earlier
  file-bridge transfer rather than a hardlink — all completing cleanly with
  no errors) before being handed off. Must be run by the user in their own
  terminal — the combined raw images across all four rounds are close to a
  terabyte, far beyond what a file-transfer bridge can move, and `--hardlink`
  only works as a local same-filesystem call.
- `relocate_round1_illum_and_profiles.sh`, `relocate_rounds_2_3_4.sh` —
  earlier, narrower predecessors of `cpg_pilot_transfer.sh` (Round-1-only
  hand-typed, then Round-2-4-only). Kept for reference/history; prefer
  `cpg_pilot_transfer.sh` going forward.
- `scripts/relocate_metadata.py` — builds `workspace/metadata/platemaps/<batch>/`
  (barcode_platemap.csv + platemap/*.txt) from this project's raw platemap
  records. Small enough (a few KB per batch) that it's run directly and
  pushed, rather than left as a script for the user — see workflow step 6.
- `scripts/validate_structure.py` — pre-upload structure checker.
- `assets/manifest.example.yaml` — starting-point manifest for cpg0041-pccma.
- `assets/manifest_round1.yaml` — real manifest for Round 1, built by hand
  from the actual `SN0313537` folder listing (Round 1's raw data isn't under
  a `Round_1_data` folder — it's under the source's original scanner-run id;
  see `manifest.example.yaml`'s comment and discussion #98) rather than
  `scan_raw_data.py`, since Round 1's 8 reimage folders are named
  `<date>_<CellLine>_Re-imaged` with no `Plate N` component, so its 9 batch
  names are given via explicit `batch_name:` overrides instead of
  round_label/plate_label/cell_line/variant concatenation. Confirmed to
  reproduce, name-for-name, the 9 batch folders and full-plate-names already
  in place on the real drive from Round 1's earlier (pre-`cpg_pilot_transfer.sh`)
  reorganization.
- `assets/manifest_round2.yaml`, `manifest_round3.yaml`, `manifest_round4.yaml`
  — real manifests for Rounds 2-4, generated by `scan_raw_data.py` against
  the actual raw folder names on the 18tbdrive and verified (2026-08-28) via
  `reorganize.py --dry-run` (zero problems, correct batch names) and a
  synthetic-skeleton `--execute --hardlink` run (see `pccma_project_notes.md`
  for how this was tested without moving real image data).
- `references/cpg_data_structure.md` — general CPG structure rules.
- `references/pccma_project_notes.md` — cpg0041-pccma-specific facts from
  the maintainer discussion.
