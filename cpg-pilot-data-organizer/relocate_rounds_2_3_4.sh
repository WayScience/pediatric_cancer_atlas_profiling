#!/bin/bash
# Run the FULL pipeline (images + illum + profiles + load_data_csv) for
# Rounds 2, 3, and 4 -- Round 1 is already done on this drive (images,
# illum across all reimage batches, and bulk+single-cell profiles were all
# verified in place earlier).
#
# WHY THIS HAS TO RUN HERE, IN YOUR OWN TERMINAL:
# The assistant session that built this cannot execute anything on this
# machine -- it only has file-transfer tools with hard size caps (~20MB per
# file, ~100MB per batch). Round 2/3/4's raw images alone are ~206G + 355G +
# 318G (~880GB combined), and --hardlink itself only works as a real
# same-filesystem call (os.link) run locally -- neither can move through a
# transfer bridge at any size. So this script, unlike the small Round 1
# illum push, has to be run by you.
#
# Everything below defaults to review-before-you-commit: each round's
# reorganize.py step is a dry run first (prints the full plan + a batch map,
# touches nothing), and this script stops (set -e) if that dry run reports
# any problems. Read that output before it moves on to --execute.
#
# Prerequisite: 18tbdrive has enough free space for a brief moment of churn
# even with --hardlink (new directory entries only, not full copies) -- if
# you haven't checked free space recently, run `df -h /media/18tbdrive`
# first (project notes say it was ~98% full / 382G free as of 2026-08-28).
#
#   chmod +x relocate_rounds_2_3_4.sh
#   ./relocate_rounds_2_3_4.sh
#
# To do just one round, comment out the others in the ROUNDS list below, or
# run its block by hand -- each round is fully independent.

set -euo pipefail

REPO="/media/18tbdrive/1.Github_Repositories/pediatric_cancer_pilot_atlas_profiling"
TARGET="/media/18tbdrive/cpg_mirror_test"
PROJECT_ID="cpg0041-pccma"
SOURCE_ID="alexslemonade"
SCRIPT_DIR="$REPO/cpg-pilot-data-organizer/scripts"
ASSET_DIR="$REPO/cpg-pilot-data-organizer/assets"
WORK_DIR="$REPO/cpg-pilot-data-organizer/.run"  # batch maps land here, not /tmp -- so they survive a reboot and you can inspect them after
mkdir -p "$WORK_DIR"

ROUNDS="2 3 4"

for r in $ROUNDS; do
    MANIFEST="$ASSET_DIR/manifest_round${r}.yaml"
    BATCH_MAP="$WORK_DIR/round${r}_batch_map.json"
    ILLUM_DIR="$REPO/1.illumination_correction/illum_directory/Round_${r}_data"
    LOADDATA_DIR="$REPO/1.illumination_correction/loaddata_csvs/Round_${r}_data"
    BULK_DIR="$REPO/3.preprocessing_features/data/bulk_profiles/Round_${r}_data"
    CONVERTED_DIR="$REPO/3.preprocessing_features/data/converted_profiles/Round_${r}_data"
    CLEANED_DIR="$REPO/3.preprocessing_features/data/cleaned_profiles/Round_${r}_data"
    SINGLE_CELL_DIR="$REPO/3.preprocessing_features/data/single_cell_profiles/Round_${r}_data"

    echo "############################################"
    echo "### Round $r"
    echo "############################################"

    echo "--- [1/4] Dry run + batch map (nothing touched yet) ---"
    python3 "$SCRIPT_DIR/reorganize.py" "$MANIFEST" --target "$TARGET" --emit-batch-map "$BATCH_MAP"
    echo "Review the plan above. Ctrl-C now if anything looks wrong."
    echo

    echo "--- [2/4] Reorganizing images (--hardlink, zero extra disk) ---"
    python3 "$SCRIPT_DIR/reorganize.py" "$MANIFEST" --target "$TARGET" --execute --hardlink
    echo

    echo "--- [3/4] Relocating illum + profiles for every plate in the batch map ---"
    python3 "$SCRIPT_DIR/relocate_illum_and_profiles.py" \
        --batch-map "$BATCH_MAP" \
        --illum-source-dir "$ILLUM_DIR" \
        --profile-source-dir "$BULK_DIR" \
        --profile-source-dir "$CONVERTED_DIR" \
        --profile-source-dir "$CLEANED_DIR" \
        --profile-source-dir "$SINGLE_CELL_DIR" \
        --target "$TARGET" --project-id "$PROJECT_ID" --source-id "$SOURCE_ID" \
        --execute --hardlink
    echo

    echo "--- [4/4] load_data_csv commands for every plate with a concatenated CSV ---"
    echo "(This step only PRINTS the commands -- it does not run them. Read each one before"
    echo " running it: relocate_load_data_csv.py refuses to write anything if a row's path"
    echo " doesn't resolve, which is exactly the kind of thing worth checking per plate rather"
    echo " than blindly looping.)"
    python3 - "$BATCH_MAP" "$LOADDATA_DIR" "$SCRIPT_DIR" "$MANIFEST" "$TARGET" "$PROJECT_ID" "$SOURCE_ID" <<'PYEOF'
import json, sys
from pathlib import Path

batch_map_path, loaddata_dir, script_dir, manifest, target, project_id, source_id = (
    Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]
)
batch_map = json.loads(batch_map_path.read_text())
for plate, batches in sorted(batch_map.items()):
    csv = loaddata_dir / f"{plate}_concatenated.csv"
    if not csv.is_file():
        continue
    batch = batches[0]
    out = f"{target}/{project_id}/{source_id}/workspace/load_data_csv/{batch}/{plate}/load_data.csv"
    print(
        f"python3 {script_dir}/relocate_load_data_csv.py "
        f"--manifest {manifest} --csv \"{csv}\" "
        f"--batch-name {batch} --plate-name {plate} --target {target} --out {out}"
    )
PYEOF
    echo
done

echo "############################################"
echo "### Done with Rounds 2-4. Next steps:"
echo "############################################"
echo "1. Scroll back up through each round's [4/4] output above and run the printed"
echo "   relocate_load_data_csv.py command for each plate -- one at a time, checking its"
echo "   output before moving to the next (it refuses to write if a row's path doesn't"
echo "   resolve, which is worth reading rather than blindly looping over)."
echo "2. Validate everything:"
echo "     python3 $SCRIPT_DIR/validate_structure.py $TARGET/$PROJECT_ID"
echo "3. Once that's clean, see SKILL.md step 7 for the aws s3 sync upload to staging."
