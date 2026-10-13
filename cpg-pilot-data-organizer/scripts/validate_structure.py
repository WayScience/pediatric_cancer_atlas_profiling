#!/usr/bin/env python3
"""
Check a locally-built CPG tree against the structure rules in
references/cpg_data_structure.md, before you hand it off to the CPG
maintainers for upload to staging.

CPG validation today is manual (a maintainer eyeballs it after you upload) --
this catches the mechanical stuff ahead of time so that review is faster and
you're not round-tripping a multi-TB upload over a naming mistake.

Usage:
    python validate_structure.py /path/to/local/cpg0041-pccma
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def check(condition: bool, ok_msg: str, fail_msg: str, results: list):
    results.append((condition, ok_msg if condition else fail_msg))


def validate(root: Path) -> tuple[list[tuple[bool, str]], list[str]]:
    results: list[tuple[bool, str]] = []
    notes: list[str] = []

    # Project id folder: exactly one child of root, [a-z0-9_] only.
    project_dirs = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    check(
        root.is_dir(),
        f"Root {root} exists",
        f"Root {root} does not exist",
        results,
    )
    if not root.is_dir():
        return results, notes

    # root itself is expected to BE the project folder (e.g. .../cpg0041-pccma)
    project_id = root.name
    check(
        bool(re.fullmatch(r"[a-z0-9_-]+", project_id)),
        f"Project id '{project_id}' uses only lowercase letters/digits/_/-",
        f"Project id '{project_id}' should only contain lowercase letters, digits, underscores, and hyphens",
        results,
    )

    source_dirs = [p for p in root.iterdir() if p.is_dir()]
    check(
        len(source_dirs) >= 1,
        f"Found {len(source_dirs)} source folder(s) under {project_id}/",
        f"No source folder found under {project_id}/ -- expected e.g. {project_id}/alexslemonade/",
        results,
    )

    for source_dir in source_dirs:
        images_dir = source_dir / "images"
        workspace_dir = source_dir / "workspace"

        check(
            images_dir.is_dir(),
            f"{source_dir.name}/images/ exists",
            f"{source_dir.name}/images/ is missing",
            results,
        )
        check(
            workspace_dir.is_dir(),
            f"{source_dir.name}/workspace/ exists",
            f"{source_dir.name}/workspace/ is missing (need at minimum workspace/load_data_csv/ and workspace/metadata/)",
            results,
        )

        if not images_dir.is_dir():
            continue

        # plate-name only needs to be unique WITHIN a batch (workspace paths
        # are backend/<batch>/<plate>/, profiles/<batch>/<plate>/, etc). A
        # barcode legitimately gets reused across batches when a plate is
        # re-imaged later under the same barcode with a new timestamp -- so
        # track per-batch uniqueness as a hard FAIL, and cross-batch reuse
        # only as an informational note.
        plate_names_seen_in_batch: dict[str, str] = {}
        plate_names_seen_globally: dict[str, set] = {}

        for batch_dir in sorted(p for p in images_dir.iterdir() if p.is_dir()):
            plate_names_seen_in_batch = {}
            check(
                bool(ALLOWED_NAME_RE.match(batch_dir.name)),
                f"Batch folder '{batch_dir.name}' name is clean (letters/digits/_/-only)",
                f"Batch folder '{batch_dir.name}' has whitespace or disallowed characters",
                results,
            )

            inner_images = batch_dir / "images"
            check(
                inner_images.is_dir(),
                f"{batch_dir.name}/images/ exists",
                f"{batch_dir.name}/images/ is missing (expected images/<batch>/images/<full-plate-name>/)",
                results,
            )
            if not inner_images.is_dir():
                continue

            plate_dirs = [p for p in inner_images.iterdir() if p.is_dir()]
            check(
                len(plate_dirs) >= 1,
                f"{batch_dir.name}/images/ contains at least one plate folder",
                f"{batch_dir.name}/images/ has no plate folders",
                results,
            )

            for plate_dir in plate_dirs:
                full_plate_name = plate_dir.name
                check(
                    bool(ALLOWED_NAME_RE.match(full_plate_name)),
                    f"Plate folder '{full_plate_name}' name is clean",
                    f"Plate folder '{full_plate_name}' has whitespace or disallowed characters "
                    "(strip spaces/special chars, e.g. 'Measurement 2' -> 'Measurement2')",
                    results,
                )
                # The plate folder should actually contain image files
                # somewhere under it -- if it doesn't, the most likely cause
                # is an unexpected extra nesting level left over from the
                # raw acquisition folder structure.
                has_files = any(f.is_file() for f in plate_dir.rglob("*"))
                check(
                    has_files,
                    f"'{full_plate_name}' contains image files",
                    f"'{full_plate_name}' has no files anywhere under it -- check for an unexpected "
                    "extra nesting level (CPG requires no double-nesting)",
                    results,
                )

                plate_name_guess = full_plate_name.split("__", 1)[0]
                if (
                    plate_name_guess in plate_names_seen_in_batch
                    and plate_names_seen_in_batch[plate_name_guess] != full_plate_name
                ):
                    check(
                        False,
                        "",
                        f"Derived plate-name '{plate_name_guess}' is not unique within batch "
                        f"'{batch_dir.name}': also used by "
                        f"'{plate_names_seen_in_batch[plate_name_guess]}' and '{full_plate_name}'",
                        results,
                    )
                else:
                    plate_names_seen_in_batch[plate_name_guess] = full_plate_name
                plate_names_seen_globally.setdefault(plate_name_guess, set()).add(batch_dir.name)

        if workspace_dir.is_dir():
            load_data_dir = workspace_dir / "load_data_csv"
            check(
                load_data_dir.is_dir() and any(load_data_dir.rglob("*.csv")),
                "workspace/load_data_csv/ exists and has at least one CSV",
                "workspace/load_data_csv/ is missing or empty -- load_data_csv is one of the "
                "three mandatory pieces (images, metadata, load_data_csv) for any deposit",
                results,
            )
            metadata_dir = workspace_dir / "metadata"
            check(
                metadata_dir.is_dir(),
                "workspace/metadata/ exists",
                "workspace/metadata/ is missing -- unblinded metadata is mandatory for any deposit",
                results,
            )

        for plate_name, batch_names in plate_names_seen_globally.items():
            if len(batch_names) > 1:
                notes.append(
                    f"plate-name '{plate_name}' is reused across batches {sorted(batch_names)} "
                    "-- normal if this barcode was re-imaged later, but double check it's not a mistake"
                )

    return results, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="Path to the local project root, e.g. ./cpg0041-pccma")
    args = ap.parse_args()

    results, notes = validate(args.root)
    n_fail = sum(1 for ok, _ in results if not ok)
    for ok, msg in results:
        print(f"{'PASS' if ok else 'FAIL'}  {msg}")

    if notes:
        print("\nNotes (informational, not failures):")
        for n in notes:
            print(f"  NOTE  {n}")

    print(f"\n{len(results) - n_fail}/{len(results)} checks passed.")
    if n_fail:
        print("Fix the FAIL lines above before handing this off for upload to staging.")
        sys.exit(1)
    print("Structure looks consistent with the CPG rules in references/cpg_data_structure.md.")


if __name__ == "__main__":
    main()
