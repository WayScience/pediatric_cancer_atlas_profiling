#!/usr/bin/env python3
"""
Relocate already-generated illumination-correction and pycytominer/CytoTable
profile outputs into the CPG workspace/ structure, for plates that have
actually been analyzed (see references/pccma_project_notes.md).

This does NOT handle backend/ or analysis/ (CellProfiler's sqlite + per-site
CSV output) yet -- that folder's internal shape (in this project:
sqlite_outputs/<round>/<barcode>/) hasn't been confirmed closely enough to
relocate it correctly. Ask the user how it's laid out before extending this
script to cover it; don't guess from a partial listing.

Two categories are supported:

  illum     <source>/<plate>_Illum<Channel>.npy
            -> <target>/<project>/<source_id>/images/<batch>/illum/<plate>/<plate>_Illum<Channel>.npy
            (matches CPG's documented pattern -- confirmed 2026-08-28 against
            data_structure.html's own example path,
            "2021_04_26_Batch1/illum/BR00117035/BR00117035_IllumDNA.npy", and
            discussion #98's example tree, "illum/BR00145439/BR00145439_IllumDNA.npy".
            illum/ contains a PER-PLATE subfolder, same as workspace/profiles.)

            --batch-name accepts MULTIPLE values for this category. Use this
            when a plate's images physically live in more than one CPG batch
            folder -- e.g. a barcode that was originally scanned AND later
            targeted-reimaged: images/Round1/images/<barcode>__... holds the
            original acquisition, and images/Round1_A673_Reimage20240717/images/<barcode>__...
            holds the reimage. Since illum lives inside images/<batch>/ (it
            travels with a batch's images, not with the analysis identity),
            every batch folder that contains this plate's images should also
            have its illum/<plate>/ subfolder, even though the underlying
            .npy content is identical everywhere (it was computed once, from
            the MERGED load_data_csv spanning all those raw folders -- see
            0.create_loaddata_csvs.py's reimage-merge logic). This is our
            best-fit reading of the documented pattern, not something CPG's
            docs or discussion #98 confirm explicitly for the multi-batch
            case -- flag it for Erin/Shantanu to confirm, same as the
            profiles format question below.

  profiles  <source-dir>/<plate>_bulk*.parquet          (well-level, pycytominer:
                                                          bulk / bulk_annotated /
                                                          bulk_normalized / bulk_feature_selected)
            <source-dir>/<plate>_converted.parquet       (single-cell, CytoTable)
            <source-dir>/<plate>_cleaned.parquet         (single-cell, post-QC)
            <source-dir>/<plate>_sc_*.parquet            (single-cell, pycytominer:
                                                          sc_annotated / sc_normalized /
                                                          sc_feature_selected -- the
                                                          single-cell-granularity mirror
                                                          of the bulk annotate/normalize/
                                                          feature-select pipeline; lives
                                                          in its own single_cell_profiles/
                                                          sibling dir, easy to miss since
                                                          it's not named like the others)
            -> <target>/<project>/<source_id>/workspace/profiles/<batch>/<plate>/<filename, unchanged>

            --source-dir accepts MULTIPLE values for this category, since in
            this project profiles live across FOUR sibling directories:
            bulk_profiles/, converted_profiles/, cleaned_profiles/, and
            single_cell_profiles/ (found 2026-08-28 -- easy to miss because
            its file NAMES don't contain "single_cell", only "sc_", and it's
            a sibling of the other three, not nested under any of them).
            Pass each one you want relocated; omit any you don't want this run.

            Unlike illum, profiles/backend/analysis are NOT duplicated across
            batches here -- pass exactly the ONE batch that owns this plate's
            analysis identity (the original/base batch, e.g. Round1, not a
            reimage batch), matching the plate's Metadata_Plate in its merged
            load_data_csv. The analysis is one merged result regardless of
            which raw folders contributed images to it, so it belongs in one
            place.

            Filenames are kept AS-IS, not renamed to CPG's documented
            "_augmented.csv.gz" convention -- confirmed against
            data_structure.html (2026-08-28): CPG's documented backend/ is
            SQLITE-only ("a single-cell SQLite file... and a CSV that
            aggregates the single-cell data into a per-well measurement"),
            with NO documented parquet convention for single-cell data
            anywhere (profiles/, backend/, and workspace_dl/ are the only
            single-cell-adjacent locations documented, and none of them
            describe CytoTable-style parquet). So placing the single-cell
            converted/cleaned parquet in workspace/profiles/ alongside the
            bulk profiles is a placeholder, not a confirmed-correct location
            -- flag this clearly for Erin/Shantanu, same as the bulk
            parquet-vs-csv.gz question.

            SIZE WARNING: single-cell parquet files in this project (converted,
            cleaned, AND sc_annotated/sc_normalized/sc_feature_selected) are
            1-13GB EACH (not MB) -- do not attempt to move these through a
            small-file transfer bridge/tool. Use --hardlink when --target is
            on the same filesystem as the source (true for this project's
            18tbdrive setup) so relocating them costs zero extra disk and is
            near-instant; run this script directly in your own terminal for
            these, not through anything that stages/uploads files elsewhere.

Usage:
    python organize_workspace.py illum \\
        --source-dir "/path/to/1.illumination_correction/illum_directory/Round_1_data/BR00143976" \\
        --target /path/to/local_cpg_mirror --project-id cpg0041-pccma --source-id alexslemonade \\
        --batch-name Round1 --batch-name Round1_A673_Reimage20240717 \\
        --batch-name Round1_CHP212_Reimage20240717 --plate-name BR00143976 --execute --hardlink

    python organize_workspace.py profiles \\
        --source-dir "/path/to/3.preprocessing_features/data/bulk_profiles/Round_1_data" \\
        --source-dir "/path/to/3.preprocessing_features/data/converted_profiles/Round_1_data" \\
        --source-dir "/path/to/3.preprocessing_features/data/cleaned_profiles/Round_1_data" \\
        --source-dir "/path/to/3.preprocessing_features/data/single_cell_profiles/Round_1_data" \\
        --target /path/to/local_cpg_mirror --project-id cpg0041-pccma --source-id alexslemonade \\
        --batch-name Round1 --plate-name BR00143976 --execute --hardlink

Defaults to a dry run (prints what would be copied); pass --execute to copy,
plus --hardlink to hardlink instead (same filesystem only, zero extra disk).
"""

from __future__ import annotations

import argparse
import errno
import os
import shutil
import sys
from pathlib import Path

from cpg_lib import sanitize_name, sanitize_project_id

PROFILE_GLOB_PATTERNS = [
    "{plate}_bulk*.parquet",
    "{plate}_converted.parquet",
    "{plate}_cleaned.parquet",
    "{plate}_sc_*.parquet",  # sc_annotated / sc_normalized / sc_feature_selected -- single_cell_profiles/
]
SINGLE_CELL_SUFFIXES = (
    "_converted.parquet",
    "_cleaned.parquet",
    "_sc_annotated.parquet",
    "_sc_normalized.parquet",
    "_sc_feature_selected.parquet",
)


def find_profile_matches(source_dirs: list[Path], plate_name: str) -> list[Path]:
    matches = []
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            sys.exit(f"--source-dir {source_dir} does not exist or is not a directory")
        for pattern in PROFILE_GLOB_PATTERNS:
            matches.extend(sorted(source_dir.glob(pattern.format(plate=plate_name))))
    return matches


def relocate(f: Path, dest: Path, hardlink: bool) -> None:
    if dest.exists():
        # Re-running this script (e.g. after it stopped partway through a
        # multi-plate loop, or after an earlier plain-copy placed some files
        # before --hardlink support existed) shouldn't blow up on files that
        # are already correctly there.
        if hardlink and dest.samefile(f):
            print(f"  (already hardlinked, skipping) {dest.name}")
            return
        if dest.stat().st_size == f.stat().st_size:
            print(
                f"  (already exists, same size -- assuming it's already correctly placed "
                f"from an earlier run, skipping) {dest.name}"
            )
            if hardlink:
                print(
                    "    NOTE: this one is a plain copy, not a hardlink (different inode) -- "
                    "it's using its own real disk space rather than sharing the source's. "
                    "Delete it and re-run with --hardlink if you want it deduplicated."
                )
            return
        sys.exit(
            f"{dest} already exists with a DIFFERENT SIZE than {f} "
            f"({dest.stat().st_size:,} bytes vs {f.stat().st_size:,} bytes) -- this looks like "
            "stale or wrong content, not just an earlier non-hardlinked copy. Refusing to "
            "overwrite -- remove it yourself first if you want to re-relocate it, or "
            "investigate what's actually there."
        )
    if hardlink:
        try:
            os.link(f, dest)
        except OSError as e:
            if e.errno == errno.EXDEV:
                sys.exit(
                    f"Hardlinking failed for {f} -> {dest}: {e}\n"
                    "This means --target is on a different filesystem/drive than the "
                    "source -- hardlinks only work within one filesystem. Drop --hardlink to "
                    "plain-copy instead (fine for illum's small files, NOT recommended for "
                    "multi-GB single-cell profile parquet -- see this script's docstring)."
                )
            sys.exit(f"Hardlinking failed for {f} -> {dest}: {e}")
    else:
        shutil.copy2(f, dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("category", choices=["illum", "profiles"], help="Which output type to relocate")
    ap.add_argument(
        "--source-dir",
        type=Path,
        action="append",
        required=True,
        help="Folder containing this plate's output files. Repeatable for 'profiles' "
        "(e.g. once each for bulk_profiles/, converted_profiles/, cleaned_profiles/); "
        "'illum' normally only needs one.",
    )
    ap.add_argument("--target", type=Path, required=True, help="Local root to mirror the gallery under")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument(
        "--batch-name",
        action="append",
        required=True,
        help="e.g. Round1 (the batch this plate's output belongs under). Repeatable for "
        "'illum' ONLY, to place the same illum files into every batch whose images/ "
        "folder contains this plate (see docstring) -- 'profiles' should get exactly one "
        "batch, its original/analysis-identity batch.",
    )
    ap.add_argument("--plate-name", required=True, help="Short plate-name / barcode, e.g. BR00145438")
    ap.add_argument("--execute", action="store_true", help="Actually copy files (default: dry run)")
    ap.add_argument(
        "--hardlink",
        action="store_true",
        help="Hardlink instead of copy (only meaningful with --execute). Same filesystem only. "
        "Strongly recommended for 'profiles' single-cell parquet (multi-GB each) and harmless "
        "for illum's small .npy files -- see this script's docstring for why.",
    )
    args = ap.parse_args()

    project_id = sanitize_project_id(args.project_id)
    source_id = sanitize_name(args.source_id)
    batch_names = [sanitize_name(b) for b in args.batch_name]
    plate_name = sanitize_name(args.plate_name)

    if args.category == "profiles" and len(batch_names) > 1:
        sys.exit(
            "profiles takes exactly one --batch-name (its analysis-identity batch) -- got "
            f"{batch_names}. Multiple --batch-name is for 'illum' only (see --help)."
        )

    source_root = args.target / project_id / source_id

    if args.category == "illum":
        source_dir = args.source_dir[0] if len(args.source_dir) == 1 else None
        if source_dir is None:
            sys.exit("'illum' takes exactly one --source-dir.")
        if not source_dir.is_dir():
            sys.exit(f"--source-dir {source_dir} does not exist or is not a directory")
        matches = sorted(source_dir.glob(f"{plate_name}_Illum*.npy"))
        if not matches:
            sys.exit(f"No files matched under {source_dir} for plate {plate_name!r} (category=illum).")
        dest_dirs = [source_root / "images" / b / "illum" / plate_name for b in batch_names]
    else:
        matches = find_profile_matches(args.source_dir, plate_name)
        if not matches:
            sys.exit(
                f"No files matched under {args.source_dir} for plate {plate_name!r} (category=profiles). "
                f"Checked patterns: {PROFILE_GLOB_PATTERNS}"
            )
        dest_dirs = [source_root / "workspace" / "profiles" / batch_names[0] / plate_name]

    verb = "Hardlinking" if args.hardlink else "Copying"
    for dest_dir in dest_dirs:
        print(f"{'Would relocate' if not args.execute else verb} {len(matches)} file(s) to {dest_dir}:")
        for f in matches:
            size_mb = f.stat().st_size / 1_000_000
            print(f"  {f.name}  ({size_mb:,.1f} MB)")
        print()

    if args.category == "profiles":
        single_cell = [f for f in matches if f.name.endswith(SINGLE_CELL_SUFFIXES)]
        if single_cell:
            total_gb = sum(f.stat().st_size for f in single_cell) / 1_000_000_000
            print(
                f"NOTE: {len(single_cell)} single-cell parquet file(s) totaling {total_gb:,.1f} GB. "
                "CPG's documented structure has no parquet convention for single-cell data -- "
                "backend/ is documented as SQLITE-only. Placing these in workspace/profiles/ "
                "alongside bulk profiles is a placeholder pending Erin/Shantanu confirmation, "
                "same as the bulk parquet-vs-csv.gz naming question. See pccma_project_notes.md."
            )
        print(
            "\nNOTE: filenames are kept as-is (e.g. '_bulk_annotated.parquet'), NOT renamed to "
            "CPG's documented '_augmented.csv.gz' convention. Confirm with the CPG maintainers "
            "whether parquet + this naming is acceptable before this goes to staging -- see "
            "references/pccma_project_notes.md."
        )

    if args.category == "illum" and len(dest_dirs) > 1:
        print(
            f"\nNOTE: relocating the SAME illum files into {len(dest_dirs)} batches "
            f"({', '.join(batch_names)}) because this plate's images live in all of them. "
            "This is our best-fit reading of CPG's documented per-batch illum/ pattern for a "
            "reimaged plate, not something confirmed explicitly by the docs or discussion #98 "
            "-- flag it for Erin/Shantanu. See this script's docstring."
        )

    if not args.execute:
        print("\nDry run only -- no files were touched. Re-run with --execute (add --hardlink if same filesystem).")
        return

    for dest_dir in dest_dirs:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in matches:
            relocate(f, dest_dir / f.name, args.hardlink)
        print(f"Done -- {'hardlinked' if args.hardlink else 'copied'} {len(matches)} file(s) to {dest_dir}")


if __name__ == "__main__":
    main()
