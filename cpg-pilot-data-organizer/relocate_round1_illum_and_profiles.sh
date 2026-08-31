#!/bin/bash
# Relocate Round 1's profiles (bulk + single-cell converted/cleaned) into the
# CPG-structured local mirror, using hardlinks (zero extra disk on the same
# filesystem).
#
# NOTE (2026-08-28): illum is NOT in this script anymore. The AI relocated
# illum for real, into every batch containing each plate, via the file
# bridge (144 files, ~4.7MB each -- small enough to transfer) and verified
# it landed correctly with device_list_dir. If you re-add an illum step and
# run it again, it will error out trying to hardlink over files that already
# exist -- that's expected, illum is done. This script now only does the
# piece the AI categorically cannot do: the single-cell profile parquet is
# 1-13GB EACH, across FOUR source directories now (bulk_profiles/,
# converted_profiles/, cleaned_profiles/, and single_cell_profiles/ -- the
# last one holds sc_annotated/sc_normalized/sc_feature_selected and was easy
# to miss since its files aren't named "single_cell" and it wasn't wired up
# until 2026-08-28). All told, Round 1's 6 barcodes are roughly 220GB of
# single-cell-scale parquet, which is 50-650x over the file-transfer
# bridge's per-file cap (~20MB), and --hardlink itself only works as a
# same-machine, same-filesystem call (os.link), not a file transfer -- so
# this step has to run in your own terminal, on the machine that has
# /media/18tbdrive mounted.
#
# Prerequisite: your Round 1 images must already be reorganized at
# --target (i.e. you've already run reorganize.py for Round 1 against this
# --target), and illum should already be in place (see note above).
#
# Edit REPO and TARGET below if your paths differ, then:
#   chmod +x relocate_round1_illum_and_profiles.sh
#   ./relocate_round1_illum_and_profiles.sh

set -euo pipefail

REPO="/media/18tbdrive/1.Github_Repositories/pediatric_cancer_pilot_atlas_profiling"
TARGET="/media/18tbdrive/cpg_mirror_test"
PROJECT_ID="cpg0041-pccma"
SOURCE_ID="alexslemonade"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts"

BULK_DIR="$REPO/3.preprocessing_features/data/bulk_profiles/Round_1_data"
CONVERTED_DIR="$REPO/3.preprocessing_features/data/converted_profiles/Round_1_data"
CLEANED_DIR="$REPO/3.preprocessing_features/data/cleaned_profiles/Round_1_data"
SINGLE_CELL_DIR="$REPO/3.preprocessing_features/data/single_cell_profiles/Round_1_data"

for plate in BR00143976 BR00143977 BR00143978 BR00143979 BR00143980 BR00143981; do
    echo "=== $plate: profiles (bulk + single-cell) -> Round1 ==="
    python3 "$SCRIPT_DIR/organize_workspace.py" profiles \
        --source-dir "$BULK_DIR" \
        --source-dir "$CONVERTED_DIR" \
        --source-dir "$CLEANED_DIR" \
        --source-dir "$SINGLE_CELL_DIR" \
        --target "$TARGET" --project-id "$PROJECT_ID" --source-id "$SOURCE_ID" \
        --batch-name Round1 --plate-name "$plate" --execute --hardlink
    echo
done

echo "All done. Verify with:"
echo "  python3 $SCRIPT_DIR/validate_structure.py $TARGET/$PROJECT_ID"
