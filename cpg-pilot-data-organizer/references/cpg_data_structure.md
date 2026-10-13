# Cell Painting Gallery — data structure reference

Source: https://broadinstitute.github.io/cellpainting-gallery/overview.html,
data_structure.html, and contributing_to_cpg.html. Read this file when you need
the general CPG rules (as opposed to `pccma_project_notes.md`, which has the
facts specific to the alexslemonade/cpg0041-pccma project).

## Top-level hierarchy

```
cellpainting-gallery/
└── <project>/            # e.g. cpg0041-pccma, cpg0000-jump-pilot —
                          # lowercase letters, digits, `_`, and `-` only
    └── <source>/         # identifier for the contributing institution,
        │                 # required even for a single-source dataset
        ├── images/
        ├── workspace/
        └── workspace_dl/  # deep-learning embeddings, usually added later
```

## `images/` (arrayed experiments — this is what Cell Painting pilots use)

```
images/
└── <batch>/
    ├── illum/
    │   └── <plate-name>/
    │       └── <plate-name>_Illum<Channel>.npy
    └── images/
        └── <full-plate-name>/
            └── <raw microscope files, untouched>
```

**illum/ has a per-plate subfolder, like workspace/profiles does** -- confirmed
against data_structure.html's own example
(`2021_04_26_Batch1/illum/BR00117035/BR00117035_IllumDNA.npy`) and discussion
#98's example tree (`illum/BR00145439/BR00145439_IllumDNA.npy`). Don't put the
`.npy` files flat in `illum/` itself -- an earlier version of this skill did
that (fixed 2026-08-28).

- `<batch>` is conventionally `YYYY_MM_DD_<batch-name>`, but the date prefix
  is **not strictly required** — plenty of real batches skip it.
- **No double nesting.** A batch is a single folder directly under `images/`.
  If your data has a natural two-level grouping (e.g. "round" and "plate"),
  concatenate it into one folder name (`Round2_Plate3_A673_Reimage`) instead
  of nesting (`Round2/Plate3_A673_Reimage`). This was a specific, repeated
  correction from the CPG maintainer in past contributions — don't nest.
- `<full-plate-name>` is whatever your acquisition software calls the plate
  folder (e.g. `BR00143976__2024-07-04T16_04_45-Measurement2`). It must
  contain no whitespace and no special characters other than `_` and `-`.
- `<plate-name>` is a **short, unique** identifier derived from
  `<full-plate-name>` — e.g. `BR00117035__2021-05-02T16_02_51-Measurement1`
  truncates to `BR00117035`. The relationship between the two must be
  "immediately obvious" (per the docs) — i.e. a deterministic prefix/split,
  not an arbitrary rename. `<plate-name>` is what shows up in `workspace/`.

## `workspace/` (arrayed)

| Folder | Contents |
|---|---|
| `analysis/<batch>/<plate>/analysis/<plate>-<well>-<site>/` | CellProfiler `Cells.csv`, `Image.csv`, `Nuclei.csv`, `outlines/` |
| `backend/<batch>/<plate>/` | `<plate>.sqlite` (single-cell), `<plate>.csv` (well-level) |
| `load_data_csv/` | LoadData CSVs pointing at S3 image URLs |
| `metadata/platemaps/<batch>/` | `barcode_platemap.csv` + `platemap/<PLATEMAP_NAME>.txt` |
| `profiles/<batch>/<plate>/` | `<plate>.csv.gz` and normalized/feature-selected variants |

`load_data_csv` requirements:
- Columns named `URL_<ChannelName>` (e.g. `URL_OrigDNA`, `URL_OrigER`), each a
  full `s3://cellpainting-gallery/...` path.
- Required columns: `Metadata_Plate`, `Metadata_Well` (and typically
  `Metadata_Site`).
- Well format follows whatever the raw filenames use (`A01`, `a1`, `a01`, ...)
  — pick one and be consistent within a plate.

`barcode_platemap.csv` columns: `Assay_Plate_Barcode` (must match the
`<plate-name>` used elsewhere), `Plate_Map_Name` (references a platemap
filename). `platemap/<NAME>.txt` needs at minimum `plate_map_name` and
`well_position` columns — this content has to come from your actual plate
design records, it can't be generated from the images alone.

## What's actually required for a pilot/early deposit

Per the contributing guide: **images, un-blinded metadata, and load_data_csv
are the minimum.** `analysis/`, `backend/`, `profiles/` etc. are for later,
once CellProfiler processing exists. Don't block a deposit on having those.

## Contribution process notes

- Folder names: strip whitespace, allow only `_` and `-`.
- Validation today is manual (done by the CPG maintainers after you upload to
  their staging bucket) — there's no automated pre-check on their end, so
  catching structure problems locally before handoff saves a review cycle.
- Data goes to a **staging bucket** on AWS with temporary credentials, not
  directly to the public `cellpainting-gallery` bucket. `load_data_csv`
  should still reference the eventual production `s3://cellpainting-gallery/...`
  path, not the staging path.
- A PR to the cellpainting-gallery repo README (Available Datasets table) is
  expected once the deposit is live.
