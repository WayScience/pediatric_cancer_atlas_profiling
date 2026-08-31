# AI skill: `cpg-pilot-data-organizer`

## Overview

The Cell Painting Gallery (CPG), run by the Broad Institute, hosts imaging datasets in one specific directory structure: a fixed hierarchy of project/source/batch/plate folders, with exact naming rules for how those folders are named, and a `load_data.csv` per plate that tells downstream tools where every image lives.
None of that matches how imaging data actually comes off the microscope: raw Opera Phenix/Harmony output is organized by scanner run and acquisition timestamp, plates get re-imaged under the same barcode with a new folder each time, and the round that became "Round 1" in this project isn't even labeled "Round 1" anywhere on disk (it's filed under a scanner-run id, `SN0313537`).

Updating the structure of the data output into the expected structure for CPG by hand for four rounds of imaging, a few dozen plates, cross-batch reimages, and several hundred GB to multiple TB of images and profiling output is exactly the kind of mechanical, detail-heavy, easy-to-get-subtly-wrong work worth automating rather than doing plate-by-plate in a terminal.
A single wrong batch name or a plate folder nested one level too deep is the sort of thing that only surfaces during the maintainers' manual review, after a multi-hundred-GB upload and expensive to redo.
This skill exists to get the structure right the first time, working from an explicit manifest of what's actually on disk rather than guessing at folder-naming patterns.

## What it's for

Built for the `cpg0041-pccma` deposit (alexslemonade / Way Lab's pediatric cancer Cell Painting atlas project), specifically for the pilot dataset including 4 rounds of imaging across a few dozen plates, but the manifest-driven approach generalizes to any arrayed Cell Painting dataset going into CPG.
It takes raw plate-imaging output plus whatever downstream pipeline outputs already exist (illumination correction, bulk/single-cell profiles) and produces a local, byte-for-byte-correct mirror of the CPG structure — images, illum, profiles, load_data_csv, and plate metadata all in the batch/plate layout CPG expects, ready to `aws s3 sync` to the maintainers' staging bucket.

## Reusing this for a new screen or the wider atlas

To use this skill, just generate new manifest describing that screen's raw folders.
`cpg_lib.py`, `reorganize.py`, `organize_workspace.py`, `relocate_illum_and_profiles.py`, `relocate_load_data_csv.py`, and `validate_structure.py` are all manifest-driven this way.
`scan_raw_data.py` auto-writes manifest entries from raw folder names, but only for this pilot's specific naming convention ("Plate N \<CellLine\> Reimage" / "Plate N All Cell Lines"); a screen with different raw-folder naming needs its manifest hand-written instead, the same fallback Round 1 and the screens above already use.
`relocate_metadata.py` is the one piece that's genuinely pilot-specific and would need real code changes, not just a new manifest, since it's hardcoded to this pilot's exact platemap CSV columns (`barcode,time_point,platemap_file` and `cell_line,row,column,well,seeding_density,condition`), so for a screen with a differently-shaped metadata record (say, `treatment`/`dose` instead of `time_point`) would need that script adjusted first.

## Where things stand for cpg0041-pccma

As of this writing, all 4 rounds have been reorganized, uploaded to CPG's staging bucket, and object counts have been verified to match between the local mirror and the bucket (542,165 objects / 1.8TB, both sides).

## Where to actually start

**`SKILL.md`** contains the documentation: the full workflow, every script's usage, the structure rules, and the project-specific facts and decisions.
This file is only the "why," not the "how."
Please read `SKILL.md` and `references/pccma_project_notes.md` before touching anything.

## Layout

```
cpg-pilot-data-organizer/
├── SKILL.md                        # the actual workflow/instructions
├── README.md                       # this file
├── cpg_pilot_transfer.sh           # one-command driver: all 4 rounds, images+illum+profiles
├── finish_load_data_csv.sh         # generated per-plate load_data_csv commands
├── relocate_round1_illum_and_profiles.sh,   # earlier, narrower predecessors of
│   relocate_rounds_2_3_4.sh                 # cpg_pilot_transfer.sh -- kept for history
├── scripts/                        # the actual Python tooling (see SKILL.md)
├── assets/                         # manifests: the source of truth for what maps where
└── references/
    ├── cpg_data_structure.md       # general CPG rules
    └── pccma_project_notes.md      # cpg0041-pccma-specific facts, decisions, and open questions
```
