# cpg0041-pccma project notes (alexslemonade / Way Lab)

Source: https://github.com/broadinstitute/cellpainting-gallery/discussions/98.
These are facts specific to this one deposit, not general CPG rules (see
`cpg_data_structure.md` for those). Read this whenever the user's task
mentions cpg0041-pccma, alexslemonade, ALSI, PCCMA, or the Round 1-4 pilot
data.

## Fixed identifiers

- **Project id:** `cpg0041-pccma`
- **Source id:** `alexslemonade` — NOT `broad`, even though imaging happened
  on Broad's Opera Phenix. This was an explicit correction from the CPG
  maintainer mid-discussion; double-check any manifest uses this value.

## What's being deposited

- Round 2, Round 3, Round 4 pilot imaging
- SK-N-AS REPO1 drug screen (`Original` and a `RowO_Repeat` re-imaging pass)
- CHP-134 REPO1 screen, plus a `CHP-134_Reupload`

## Round 1 is not named "Round 1"

There is no folder literally called "Round 1" anywhere. Round 1 pilot data
lives locally under the identifier **`SN0313537`**. Any manifest or script
that tries to find rounds by matching a "Round" pattern in folder names will
silently skip Round 1 — it must be mapped explicitly (e.g.
`round_label: Round1, raw_source: SN0313537`).

## Approved final folder structure (agreed with CPG maintainer)

```
cpg0041-pccma/
└── alexslemonade/
    └── images/
        ├── Round2_Plate3_A673_Reimage/
        ├── Round2_Plate3_<cellline>_Reimage/
        ├── SK-N-AS_REPO1_Screen_Original/
        ├── SK-N-AS_REPO1_Screen_RowO_Repeat/
        ├── CHP-134_REPO1_Screen/
        └── CHP-134_Reupload/
```

Each of these is a single, flat batch folder directly under `images/` (see
the "no double nesting" rule) — the round/plate/cell-line/variant info is all
concatenated into the folder name with underscores.

## Raw folder naming on the source server/drive

Confirmed against the real drive at `/media/18tbdrive/ALSF_pilot_data/`:

```
ALSF_pilot_data/
├── SN0313537/              # Round 1 (see above -- not literally named "Round 1")
├── Round_2_data/
├── Round_3_data/
├── Round_4_data/
├── SN0306333/              # "Atlas" data -- NOT in the approved upload list, exclude
└── incomplete-broken-data/ # exactly what it says -- exclude
```

Raw acquisition output uses PerkinElmer Opera Phenix/Harmony-style names,
e.g. `BR00143976__2024-07-04T16_04_45-Measurement 2` — note these can contain
a space before the trailing measurement number, which must be stripped per
the CPG whitespace rule before the folder becomes the `<full-plate-name>`.

**Each Measurement folder has one more nesting level inside it**, confirmed
against real data: `Assaylayout/`, `FFC_Profile/`, and `Images/` — the
actual tiffs (tens of thousands per plate) live in `Images/`, not directly
in the Measurement folder. `reorganize.py` copies this whole raw subtree
through unchanged (the safest default — it's the verbatim raw microscope
output), and `generate_load_data_csv.py` searches recursively and preserves
the `Images/` path segment in the S3 URLs it builds, rather than assuming a
flat layout.

Within `Round_2_data/`, `Round_3_data/`, `Round_4_data/`, folders are named
`Plate <N> All Cell Lines` (the original full-plate scan, which can contain
multiple plate barcodes) or `Plate <N> <CellLine> Reimage` (a targeted
re-image of one cell line's wells). Within `SN0313537/` (Round 1), the
original plates are bare barcode folders directly under it, and targeted
re-images are dated folders named `YYYYMMDD_<CellLine>_Re-imaged` (no
"Plate N" label — Round 1 didn't use that convention). See
`scripts/scan_raw_data.py`, which parses both conventions automatically.

**Barcodes get reused across a plate's original scan and its later
re-image** — e.g. barcode `BR00145439` appears both in a `...AllCellLines`
batch and again in a `..._Reimage` batch, with a different acquisition
timestamp each time. This is normal, not a mistake; `reorganize.py` and
`validate_structure.py` treat cross-batch reuse as informational, not a
failure (they only hard-fail on a collision *within* one batch).

## LoadData CSV generation is by pe2loaddata, not this skill's own script

**Confirmed (2026-08-28) against the real pipeline** (`1.illumination_correction/`
in the project repo):

- The channel→stain mapping is **by channel NAME**, from Harmony's Index.idx.xml
  metadata, via `config_files/config.yml` — NOT by the numeric channel ID
  embedded in Opera Phenix filenames (`...-ch5sk1fk1fl1.tiff`). The config's
  own comment explains why: "regardless of the channel ID number, the names
  will keep the LoadData CSVs consistent" — channel-ID-to-stain assignment
  isn't stable across imaging/reimaging sessions. **Do not use
  `scripts/generate_load_data_csv.py`'s `--channel-map N=NAME` for this
  project** — it maps by numeric ID and will silently mismatch a channel if
  the ID assignment ever shifts between sessions. That script is kept only as
  a fallback for a dataset that has no Harmony XML metadata / pe2loaddata
  setup at all.
- `nbconverted/0.create_loaddata_csvs.py` is the real generator: for each raw
  Measurement folder it calls pe2loaddata (`loaddata_utils.create_loaddata_csv`)
  with `config.yml`, producing one CSV per folder, **then merges all folders for
  one physical barcode into a single `<barcode>_concatenated.csv`**: it
  concatenates every folder's rows, tags each with `Metadata_Reimaged`
  (True/False from the folder name), sorts Reimaged-first, and
  `drop_duplicates(subset=[Well, Site], keep="first")` — so wherever a well was
  reimaged, the reimaged row wins and the original (poor-quality) row for that
  same well+site is dropped; wells never reimaged pass through unchanged from
  the original folder. **Verified correct** (reviewed the logic and confirmed
  against the real `BR00143976_concatenated.csv`, 2160 rows, 687 tagged
  Reimaged=True, spanning 5 raw folders with zero unresolved paths) — the one
  precondition it depends on is that two different reimage folders for the
  same barcode never target the same well, which holds here because a reimage
  folder targets one cell line's wells and each well belongs to one cell line.
- This literal script hardcodes `batch_name = "Round_4_data"` and discovers
  plates via `index_directory.glob("Plate *")`, which only matches the
  Round2/3/4 naming convention. **Round 1 (`SN0313537`) does NOT use "Plate N"
  folders** (see above) — yet `loaddata_csvs/Round_1_data/BR00143976_concatenated.csv`
  etc. already exist on disk for all 6 base Round 1 barcodes, along with
  matching `illum_directory/Round_1_data/<barcode>/` and
  `3.preprocessing_features/data/bulk_profiles/Round_1_data/<barcode>_bulk*.parquet`
  outputs. So a Round-1-adapted version of this discovery logic was run at
  some point (not the literal script shown above) — ask Jenna to confirm
  which script/parameters actually produced the Round 1 outputs if the
  discovery logic ever needs to be re-run or extended to a 5th round.
- **This corrects decision #1 below**: reimaged wells are not "images only" —
  their pixels get pulled into the ORIGINAL barcode's merged analysis CSV
  (`Metadata_Plate` is forced to the bare barcode for every row regardless of
  which folder it came from). So illum/backend/analysis/profiles for a plate
  like `BR00143976` correctly live under the **original** batch (`Round1`),
  even though some of its images physically live under separate reimage batch
  folders (`Round1_A-673_Reimage20240717`, etc.) — see
  `scripts/relocate_load_data_csv.py` below, which is built exactly around
  this: it rewrites each row's local `PathName_<Channel>`/`FileName_<Channel>`
  into a `URL_<Channel>` by matching that row's actual local path against the
  manifest, so a single load_data.csv can correctly reference images living in
  several different CPG batch folders.

## Existing pipeline outputs (gitignored, in the project repo)

The project repo already has CellProfiler illumination correction and a
pycytominer profiling pipeline run against Round 2 (and likely other
rounds) — output is gitignored so it doesn't show up on GitHub, but exists
locally. Repo layout (local folder name is
`pediatric_cancer_pilot_atlas_profiling`, which doesn't exactly match its
GitHub name):

```
pediatric_cancer_pilot_atlas_profiling/
├── 0.download_data/metadata/platemaps/     # Assay_Plate<N>_platemap.csv (one per physical plate 1-13) + Barcode_platemap_pilot_data.csv
├── 1.illumination_correction/
│   ├── illum_directory/Round_N_data/<plate-name>/<plate-name>_Illum<Channel>.npy   # Channel in {AGP,Brightfield,DNA,ER,Mito,RNA}
│   └── loaddata_csvs/Round_N_data/<plate-name>_concatenated.csv
├── 2.feature_extraction/
│   ├── analysis.cppipe, sqlite_outputs/Round_N_data/<plate-name>/...   # per-well/site analysis outputs, matches CPG's analysis/ pattern
│   └── loaddata_csvs/Round_N_data/...
└── 3.preprocessing_features/data/
    ├── converted_profiles/Round_N_data/<plate-name>_converted.parquet   # CytoTable single-cell output
    ├── cleaned_profiles/Round_N_data/<plate-name>_cleaned.parquet       # post-QC single-cell
    ├── bulk_profiles/Round_N_data/<plate-name>_bulk[.parquet | _annotated.parquet | _normalized.parquet | _feature_selected.parquet]
    └── single_cell_profiles/Round_N_data/<plate-name>_sc_[annotated | normalized | feature_selected].parquet
        # single-cell-granularity mirror of the bulk annotate/normalize/feature-select
        # pipeline -- found 2026-08-28, easy to miss: sibling of the other three dirs,
        # not nested under any of them, and its filenames say "sc_" not "single_cell".
        # 1-13GB EACH; present for all 4 rounds, all barcodes.
```

Decisions confirmed with the user (2026-08-28):

1. ~~Everything here is keyed by round + bare plate barcode, not by the CPG
   batch-name concept; only the originally-analyzed "All Cell Lines" plates
   get illum/backend/analysis/profiles entries; re-imaged plates contribute
   images only.~~ **Superseded (2026-08-28)** — see "LoadData CSV generation
   is by pe2loaddata" above. Everything IS keyed by round + bare barcode
   (that part was right), but re-imaged plates are not images-only: their
   well data gets merged into the base barcode's analysis via
   `0.create_loaddata_csvs.py`'s reimage-merge logic. So `illum`/`backend`/
   `analysis`/`profiles` for a barcode go under its **original** batch (e.g.
   `Round1`, `Round2_Plate3`), same as before — the correction is just that
   the accompanying `load_data_csv` for that plate legitimately references
   images living in several different `images/<batch>/` folders at once
   (original + however many reimages), not only its own batch's folder.
   `scripts/relocate_load_data_csv.py` builds the per-row URLs to handle
   exactly that.
2. CPG's documented `profiles/` pattern uses `.csv.gz` with specific suffix
   names (`_augmented`, `_normalized`, `_normalized_feature_select_plate`,
   etc). This pipeline produces `.parquet` with different suffix names
   (`_bulk_annotated`, `_bulk_normalized`, `_bulk_feature_selected`).
   **Decision: don't convert.** Relocate the parquet files as-is and flag
   the format/naming mismatch for the user to raise with Erin/Shantanu
   before actual upload — CPG does use parquet elsewhere
   (`profiles_assembled/`), so this may simply be fine, but it hasn't been
   confirmed.
3. **Exclude `SN0306333` (Atlas / `PedMap_CpStd_Atlas`) and
   `incomplete-broken-data/` entirely** — neither was in the approved
   upload list from discussion #98. Don't let `scan_raw_data.py` or any
   manifest include them without the user explicitly re-opening that
   question.
5. **Illum duplicated across every batch containing that plate (2026-08-28, pending Erin's confirmation)**:
   since illum lives inside `images/<batch>/`, and a reimaged plate's images
   physically exist in multiple batch folders (e.g. `Round1` and
   `Round1_A673_Reimage20240717`), every one of those batches now gets the
   SAME illum files under its own `illum/<plate>/` subfolder --
   `organize_workspace.py illum` takes multiple `--batch-name` values for
   exactly this. This is our best-fit reading of the documented
   per-batch-per-plate illum pattern, not something CPG's docs or discussion
   #98 confirm explicitly for the multi-batch case -- Erin/Shantanu should
   weigh in before this is treated as final (see the flag `organize_workspace.py`
   prints whenever it does this). Profiles/backend/analysis are NOT
   duplicated this way -- they represent one merged analysis result and stay
   under the plate's single original/base batch only.
6. **Single-cell profiles added alongside bulk (2026-08-28, pending Erin's
   confirmation)**: confirmed against `data_structure.html` that CPG's
   documented structure has NO parquet convention for single-cell data
   anywhere -- `backend/` is documented as SQLITE-only ("a single-cell
   SQLite file... and a CSV that aggregates the single-cell data into a
   per-well measurement"), and `profiles/` is documented as well-level/bulk
   only. So relocating single-cell parquet into
   `workspace/profiles/<batch>/<plate>/` alongside the bulk profiles is a
   placeholder, not a confirmed-correct location -- flag this for
   Erin/Shantanu same as the bulk parquet-vs-`.csv.gz` question. There are
   TWO single-cell sources, not one -- easy to miss the second:
   `_converted.parquet`/`_cleaned.parquet` (CytoTable, in `converted_profiles/`
   and `cleaned_profiles/`), and `_sc_annotated.parquet`/`_sc_normalized.parquet`/
   `_sc_feature_selected.parquet` (the single-cell-granularity mirror of the
   bulk annotate/normalize/feature-select pipeline, in its own
   `single_cell_profiles/` sibling dir -- not found until the user pointed out
   the annotated/normalized/feature-selected single-cell files were missing
   from a first pass that only wired up `converted_profiles/`/`cleaned_profiles/`).
   **Size note**: these files are 1-13GB EACH (not MB) -- for Round 1's 6
   barcodes alone, all single-cell-scale profiles combined are roughly 220GB.
   `organize_workspace.py profiles` takes multiple `--source-dir` values (one
   each for `bulk_profiles/`, `converted_profiles/`, `cleaned_profiles/`,
   `single_cell_profiles/`) and supports `--hardlink`, which is mandatory in
   practice for files this size on a space-constrained drive. See
   `relocate_round1_illum_and_profiles.sh` for a ready-to-run script covering
   all 6 Round 1 barcodes across all four source directories.
7. **Rounds 2-4 verified against real raw folder names (2026-08-28)**: confirmed
   via the real drive (`ALSF_pilot_data/Round_2_data`, `Round_3_data`,
   `Round_4_data`) that all three use the "Plate N ..." convention documented
   above, with NO unrecognized folder names (`scan_raw_data.py` would print
   these to stderr rather than silently skip them -- none appeared). Real
   per-plate barcode listings were pulled for every "All Cell Lines"/"Reimage"
   folder across all 3 rounds (45 folders total) and used to build a synthetic
   empty-directory skeleton (same names, no image data) to run
   `scan_raw_data.py` and `reorganize.py --dry-run`/`--execute --hardlink` for
   real against, without moving any actual microscopy images. Results: batch
   counts matched the real listing exactly (Round2: 15 batches/41 plates,
   Round3: 22/65, Round4: 8/24), zero problems reported (no missing sources, no
   duplicate plate-names within a batch), and a real hardlink pass (then a
   rerun) both completed cleanly. `assets/manifest_round2/3/4.yaml` are the
   resulting manifests with real `raw_source` paths substituted in for the
   synthetic ones, ready to run for real. **Known real barcode reuse (not a
   bug)**: some Reimage batches don't cover every barcode from their plate's
   "All Cell Lines" batch (e.g. Round2 Plate3's A673/CHLA-10/SK-N-DZ/SK-N-MC
   reimages each cover only 2 of that plate's 3 barcodes, and Round3 Plate6's
   CHLA-186 reimage covers only 2 of 3) -- `reorganize.py`'s per-plate batch
   map naturally handles this since it's keyed by which batches each specific
   barcode actually appears in, not by which batches its plate has in general.
8. **`reorganize.py --emit-batch-map` replaces hand-typing the illum
   cross-batch mapping (2026-08-28)**: the original Round 1 relocation script
   required manually reading the manifest and transcribing which reimage
   batches contained which barcode into a bash associative array -- exactly
   the kind of manual step that produces bugs when repeated for 3 more
   rounds with dozens of reimage batches each. `reorganize.py` already
   computes this internally (to print its "NOTE: plate-name reused across
   batches" lines); `--emit-batch-map <path.json>` now dumps it as
   `{plate_name: [batch_name, ...]}` for every multi-batch plate, and
   `scripts/relocate_illum_and_profiles.py` consumes that JSON directly --
   looping every plate, calling `organize_workspace.py illum` with the full
   batch list and `profiles` with just the base batch (always
   `batches[0]` once sorted, since `build_batch_name()` appends
   cell_line/variant AFTER round+plate, making the base name a strict prefix
   of every reimage variant). Verified against the Round 2 synthetic
   skeleton: correct per-plate batch lists, correct base-batch routing for
   profiles, and a full execute+rerun cycle completed cleanly (246 illum
   files + 24 profile files for 6 plates, matching hand-computed expected
   counts exactly). Prefer this script over hand-typed per-round bash for
   ALL rounds going forward, Round 1 included.
9. **`reorganize.py --hardlink` had the same rerun-safety bug as
   `organize_workspace.py` (2026-08-28, fixed)**: it caught any `OSError`
   from a failed hardlink and always reported "different filesystem",
   including when the real cause was simply that the destination file
   already existed (e.g. rerunning after a partial pass). Fixed the same way
   as `organize_workspace.py`'s `relocate()`: skip cleanly if the existing
   file is already the same hardlink or the same size, only hard-fail on a
   genuine size mismatch or a real cross-device (`errno.EXDEV`) error.
   Verified with a real execute-then-rerun cycle against the Round 2
   skeleton (second run exits 0, no files touched twice).
10. **Not yet resolved**: the internal structure of `sqlite_outputs/Round_N_data/<barcode>/`
   (CPG's `backend/` + `analysis/` equivalent) hasn't been fully inspected —
   a non-recursive listing of just one barcode folder was too large to
   enumerate (thousands of entries), consistent with CellProfiler's
   per-well-per-site analysis output, but the exact split between the
   `.sqlite`/well-level-CSV backend content and the per-site analysis CSVs
   isn't confirmed. Ask the user directly (they built this pipeline) rather
   than inferring it from a partial listing before writing a mover for this
   piece.

## Disk space (checked 2026-08-28)

Raw pilot round sizes: Round2 = 206G, Round3 = 355G, Round4 = 318G,
Round1/SN0313537 = 176G (≈1.06TB total). The drive itself
(`/media/18tbdrive`, 17T total) is already ~98% full with only **382G
free**. A plain copy of Round3 alone would leave ~27G of slack — too tight
to run blind on an already-strained drive. Since the local CPG-structured
mirror and the raw data live on the same filesystem, use
`reorganize.py --hardlink` (zero extra disk usage) rather than a plain
copy for this project's real run. Process one round at a time regardless
(don't run multiple rounds' reorganization concurrently), and check
`df -h /media/18tbdrive` between rounds.

## Status

As of this writing, `cpg0041-pccma` has not yet appeared in the public
`cellpainting-gallery` S3 bucket — it's still moving through the maintainer's
staging bucket. Don't assume production S3 paths are live; `load_data_csv`
should reference the eventual production path anyway (that's what the CSV
will need once the data goes public), but nothing should be uploaded directly
to the public bucket.

## Uploading the finished local mirror to staging (researched 2026-08-28)

Confirmed against [uploading_to_cpg.html](https://broadinstitute.github.io/cellpainting-gallery/uploading_to_cpg.html)
(linked from discussion #98 itself, not otherwise indexed/public): the actual
upload mechanism is deliberately not public docs -- credentials are handed
out per-prefix directly by Erin/Shantanu over email, not self-service. Once
you have them: generate a 12h-scoped read/write token via
`aws s3control get-data-access --target "s3://staging-cellpainting-gallery/cpg0041-pccma/*" ...`,
export it, then a single `aws s3 sync ./local_cpg_mirror/cpg0041-pccma
s3://staging-cellpainting-gallery/cpg0041-pccma/ --region us-east-1` does the
actual copy -- genuinely easy, because the local tree this skill builds
already matches the final structure byte-for-byte, no transformation needed
at upload time. `sync` is resumable (skips already-uploaded files), so a
12h token expiring mid-upload on a multi-hundred-GB round just means
regenerating a token and re-running the same command. See SKILL.md's
workflow step 8 for the full command sequence. This step is the user's to
run in their own terminal with their own credentials -- never draft or run
it with real AWS credentials in an assistant session.

## workspace/metadata/ was missing entirely (found + built 2026-08-28)

`validate_structure.py` hard-fails without `workspace/metadata/` -- one of
CPG's three mandatory pieces alongside images and load_data_csv -- but
nothing in this skill built it until now; it was simply missed while
images/illum/profiles/load_data_csv were being worked out. Found the raw
source at `0.download_data/metadata/` in the project repo:
`platemaps/Barcode_platemap_pilot_data.csv` (barcode,time_point,platemap_file
-- maps every barcode across all 4 rounds to which plate-design CSV it uses)
and `platemaps/Assay_Plate<N>_platemap.csv` (cell_line,row,column,well,
seeding_density,condition -- one row per well, one file per physical plate
design, 13 total for cpg0041-pccma's 12 batches).

Confirmed CPG's expected shape directly against
[data_structure.html](https://broadinstitute.github.io/cellpainting-gallery/data_structure.html)
rather than assuming: `metadata/platemaps/<batch>/barcode_platemap.csv`
(comma-separated, exactly `Assay_Plate_Barcode`/`Plate_Map_Name`, many-to-one
allowed) + `metadata/platemaps/<batch>/platemap/<Plate_Map_Name>.txt`
(TAB-separated, minimum `plate_map_name`/`well_position` plus whatever else
is useful). Wrote `scripts/relocate_metadata.py` to do this transform. Two
things worth remembering:

- Metadata lives only in the base batch (`batches[0]`), same reasoning as
  profiles/backend/analysis -- a plate's physical design doesn't change when
  it's reimaged, so there's nothing to duplicate into reimage batches.
- Round 1's single `Round1` batch actually spans TWO plate designs
  (Assay_Plate1 and Assay_Plate2), one for each set of 3 of its 6 barcodes --
  confirmed against the barcode CSV rather than assumed 1:1. Every other
  batch is a clean 3-barcodes-to-1-platemap.
- `time_point` (24h/48h/72h, per barcode) has no slot in CPG's schema and is
  dropped from `barcode_platemap.csv` rather than silently reshaped into
  something CPG didn't ask for -- flag for Erin/Shantanu whether it belongs
  elsewhere (e.g. an extra `load_data_csv` column).
- Caught and fixed a real bug before delivering: Python's `csv` module
  defaults to `\r\n` line endings regardless of platform, which would have
  embedded a literal `\r` in every line of the `.txt` platemap files --
  fixed by passing `lineterminator="\n"` explicitly. Found it via the
  script's own rerun-safety check (a file it had just written looked
  "different" on the very next run, because `Path.read_text()`'s universal-
  newline handling strips `\r\n` back to `\n` on read but the in-memory
  string being compared against still had the literal `\r\n`).

Unlike images/illum/profiles, this data is small (a few KB per batch, not
GB) -- built and pushed directly into `workspace/metadata/` on the user's
drive in this session rather than left as a script for the user to run.

## Contacts

CPG maintainer side: Erin Weisbart (@ErinWeisbart), Shantanu Singh
(@gwaybio). Way Lab / project side: Jenna Tomkinson (@jenna-tomkinson).
