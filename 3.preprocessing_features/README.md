# Preprocessing morphology features

In this module, we perform preprocessing of the features extracted from CellProfiler using CytoTable (format SQLite output as parquet merged single-cells), coSMicQC (single-cell quality control), and pycytominer (annotation, aggregation, normalize, and feature selection).

It took approximately **5 hours** to preprocess the data across all of the notebooks.
We are using a Linux-based machine running Pop_OS! LTS 22.04 with an AMD Ryzen 7 3700X 8-Core Processor with 16 CPUs and 125 GB of MEM.

## Perform preprocessing

You can perform the preprocessing of morphology features using the command below:

```bash
# Make sure you are in the 3.preprocessing_features directory
source run_preprocessing.sh
```

Before you run it, set the round of data to process: `ROUND` in `run_preprocessing.sh` (for example `Round_4_data`) and `round_id` at the top of each notebook, which must match.
The script also reads the plate list from an absolute path on the lab machine (`PARENT_FOLDER`), so point it to the `2.feature_extraction/sqlite_outputs/<round>` folder on your machine.

## Steps

The notebooks run in order, once per round (steps 0 and 1 once per plate, using `papermill` to set `plate_id`).

| Step | Notebook                                                          | What it does                                                                                              | Output                                                                                                  |
| :--- | :---------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| 0    | [`0.convert_cytotable.ipynb`](./0.convert_cytotable.ipynb)         | Converts each plate's CellProfiler SQLite file to merged single-cell parquet with CytoTable.             | `data/converted_profiles/<round>/<plate>_converted.parquet`                                             |
| 1    | [`1.sc_quality_control.ipynb`](./1.sc_quality_control.ipynb)       | Single-cell QC with coSMicQC: flags outlier single cells by z-score on AreaShape and Intensity features (for example, overlapping nuclei with high mass displacement and intensity). | `data/cleaned_profiles/<round>/<plate>_cleaned.parquet`, `qc_results/<round>/<plate>_failed_qc_indices.csv.gz`, `qc_figures/<round>/` |
| 2    | [`2.bulk_processing.ipynb`](./2.bulk_processing.ipynb)             | Aggregates the cleaned single cells to well-level bulk profiles, annotates them with the platemaps (from [`0.download_data/metadata/platemaps`](../0.download_data/metadata/platemaps/)), normalizes, and feature selects. | `data/bulk_profiles/<round>/<plate>_bulk.parquet`, `_bulk_annotated`, `_bulk_normalized`, and `_bulk_feature_selected` |
| 3    | [`3.single_cell_processing.ipynb`](./3.single_cell_processing.ipynb) | Annotates, normalizes, and feature selects the cleaned single-cell profiles.                            | `data/single_cell_profiles/<round>/<plate>_sc_annotated.parquet`, `_sc_normalized`, and `_sc_feature_selected` |
| 4    | [`4.sc_qc_report.ipynb`](./4.sc_qc_report.ipynb)                   | Builds the QC report: the cell line, seeding density, and time point with the percentage of failed single cells. | `qc_report/<round>_qc_report.parquet`                                                                   |

The `<round>` folders are `Round_1_data` through `Round_4_data`.
The large single-cell folders (`converted_profiles`, `cleaned_profiles`, and `single_cell_profiles`) are not committed; the bulk profiles, the QC results, figures, and reports are.

- **Bulk profiles** (`data/bulk_profiles/<round>/`) have four files per plate: `<plate>_bulk.parquet` (aggregated per well), `_bulk_annotated` (with the platemap), `_bulk_normalized`, and `_bulk_feature_selected`, which is the input to the [optimization module](../4.optimization/).
- **`qc_results/`** has `<plate>_failed_qc_indices.csv.gz`, the single cells that failed QC. The Round 1 files are directly in this folder, while the notebook now writes to `qc_results/<round>/` (Rounds 2 to 4 are in subfolders).
- **`qc_figures/<round>/`** has two figures per plate: `<plate>_cluster_nuclei_outliers.png` (overlapping nuclei flagged by mass displacement and intensity) and `<plate>_nuclei_solidity_outliers_histogram.png`.
- **`qc_report/<round>_qc_report.parquet`** has one row per plate and condition: `Metadata_cell_line`, `Metadata_seeding_density`, `Metadata_time_point`, `Metadata_condition`, `Metadata_Plate`, `total_nuclei_segmented`, `total_failed_qc`, and `percentage_failing_cells`.
