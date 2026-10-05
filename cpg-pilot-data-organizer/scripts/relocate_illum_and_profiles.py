#!/usr/bin/env python3
"""
Round-agnostic driver for organize_workspace.py illum + profiles, built on
top of reorganize.py's --emit-batch-map output instead of a hand-typed
per-round mapping.

Why this exists: the first version of this (for Round 1 only) was a
hand-typed bash associative array mapping each barcode to its list of
batches -- built by manually reading manifest_round1.yaml and transcribing
which reimage batches contained which barcode. That's exactly the kind of
manual-transcription step that produces bugs (and did -- see
pccma_project_notes.md's history of fixes this session). reorganize.py
already computes this exact mapping internally (to print its "NOTE:
plate-name reused across batches" lines) via --emit-batch-map, so this
script consumes that JSON instead of requiring anyone to re-derive it by
hand for Round 2, 3, 4, or any future round.

For each plate_name in the batch map:
  - illum:    organize_workspace.py illum --batch-name <every batch for this
              plate>. Illum lives inside images/<batch>/, so it needs to be
              duplicated into every batch whose images/ folder contains this
              plate's images (see organize_workspace.py's docstring).
  - profiles: organize_workspace.py profiles --batch-name <the base/original
              batch only> -- always batches[0], since --emit-batch-map sorts
              each plate's batch list, and build_batch_name() in cpg_lib.py
              always builds the base batch name from round_label+plate_label
              alone, THEN appends cell_line/variant for any reimage -- so the
              base batch name is always a strict string-prefix of every
              reimage variant sharing the same round+plate, and a prefix
              always sorts first alphabetically. Profiles/backend/analysis
              represent ONE merged analysis result and are never duplicated
              across batches (confirmed against 0.create_loaddata_csvs.py's
              reimage-merge logic -- see pccma_project_notes.md).

Usage:
    # 1. Generate the batch map (dry run is fine -- no --execute needed):
    python reorganize.py manifest_round2.yaml --target /path/to/mirror \\
        --emit-batch-map /tmp/round2_batch_map.json

    # 2. Relocate illum + profiles for every plate in that map:
    python relocate_illum_and_profiles.py \\
        --batch-map /tmp/round2_batch_map.json \\
        --illum-source-dir "/path/to/1.illumination_correction/illum_directory/Round_2_data" \\
        --profile-source-dir "/path/to/3.preprocessing_features/data/bulk_profiles/Round_2_data" \\
        --profile-source-dir "/path/to/3.preprocessing_features/data/converted_profiles/Round_2_data" \\
        --profile-source-dir "/path/to/3.preprocessing_features/data/cleaned_profiles/Round_2_data" \\
        --profile-source-dir "/path/to/3.preprocessing_features/data/single_cell_profiles/Round_2_data" \\
        --target /path/to/mirror --project-id cpg0041-pccma --source-id alexslemonade \\
        --execute --hardlink

Note: --illum-source-dir is the ROUND-level directory (one subfolder per
plate, <plate>/), not a single plate's folder -- this script appends
/<plate_name> itself for each plate in the batch map.

--emit-batch-map includes every plate in the manifest, reimaged or not -- a
plate imaged only once just gets a single-element batch list, so it still
gets its illum/profiles correctly placed in its one batch with no special
casing needed here.

Defaults to a dry run (delegates to organize_workspace.py's own dry-run
printing for every plate); pass --execute to actually relocate. A single
plate's profiles/illum failing (e.g. outputs not generated yet for that
plate) does not stop the rest of the round -- failures are collected and
reported at the end, with a non-zero exit code if any occurred.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--batch-map", type=Path, required=True,
        help="JSON from reorganize.py --emit-batch-map: {plate_name: [batch_name, ...]}",
    )
    ap.add_argument(
        "--illum-source-dir", type=Path, required=True,
        help="Round-level illum_directory/Round_N_data containing one subfolder per plate",
    )
    ap.add_argument(
        "--profile-source-dir", type=Path, action="append", required=True,
        help="Repeatable -- one per profile sibling dir (bulk_profiles/, converted_profiles/, "
        "cleaned_profiles/, single_cell_profiles/), each Round_N_data",
    )
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--execute", action="store_true", help="Actually relocate (default: dry run only)")
    ap.add_argument("--hardlink", action="store_true", help="Hardlink instead of copy (only meaningful with --execute)")
    ap.add_argument(
        "--only-plate", action="append",
        help="Restrict to these plate name(s) -- useful to test one plate before running the whole round",
    )
    args = ap.parse_args()

    batch_map = json.loads(args.batch_map.read_text())
    if not batch_map:
        sys.exit(f"{args.batch_map} is empty -- no multi-batch plates found (check it was generated correctly).")

    script_dir = Path(__file__).resolve().parent
    plates = args.only_plate or sorted(batch_map)
    failures = []

    for plate in plates:
        if plate not in batch_map:
            sys.exit(f"Plate {plate!r} not found in {args.batch_map} (known plates: {sorted(batch_map)})")
        batches = batch_map[plate]
        base_batch = batches[0]

        illum_dir = args.illum_source_dir / plate
        if illum_dir.is_dir():
            cmd = [
                sys.executable, str(script_dir / "organize_workspace.py"), "illum",
                "--source-dir", str(illum_dir),
                "--target", str(args.target), "--project-id", args.project_id, "--source-id", args.source_id,
                "--plate-name", plate,
            ]
            for b in batches:
                cmd += ["--batch-name", b]
            if args.execute:
                cmd.append("--execute")
            if args.hardlink:
                cmd.append("--hardlink")
            print(f"=== {plate}: illum -> {batches} ===")
            result = subprocess.run(cmd)
            if result.returncode != 0:
                failures.append(f"{plate}: illum failed (see output above)")
        else:
            print(f"=== {plate}: SKIPPING illum -- no folder at {illum_dir} ===")

        cmd = [sys.executable, str(script_dir / "organize_workspace.py"), "profiles"]
        for d in args.profile_source_dir:
            cmd += ["--source-dir", str(d)]
        cmd += [
            "--target", str(args.target), "--project-id", args.project_id, "--source-id", args.source_id,
            "--batch-name", base_batch, "--plate-name", plate,
        ]
        if args.execute:
            cmd.append("--execute")
        if args.hardlink:
            cmd.append("--hardlink")
        print(f"=== {plate}: profiles -> {base_batch} ===")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            failures.append(f"{plate}: profiles failed (see output above)")
        print()

    if failures:
        print(f"{len(failures)} of {len(plates)} plate(s) had a failure:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {len(plates)} plate(s) processed successfully.")


if __name__ == "__main__":
    main()
