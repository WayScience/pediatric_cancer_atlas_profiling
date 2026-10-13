# Optimization

In this module, we use the bulk profiles from the preprocessing module to determine which seeding density and time point gave the best (most reproducible) morphology profiles for each cell line.
The pilot plates vary cell line, seeding density (1000, 2000, 4000, 8000, and 12000 cells per well), time point (24, 48, and 72 hours), and plating condition, so for each cell line we look for the condition where replicate wells agree the most.

## Analysis

| Step | Notebook                                                       | Script                                                                | What it does                                                                                                                                                                                                                                    |
| :--- | :------------------------------------------------------------- | :-------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | [`0.pairwise-compare.ipynb`](./0.pairwise-compare.ipynb)         | [`scripts/0.pairwise-compare.py`](./scripts/0.pairwise-compare.py)     | For each plate's feature selected bulk profiles, computes pairwise Pearson's correlation between wells of the same cell line, seeding density, and time point. A shuffled copy of the profiles (features shuffled within each time point) is compared the same way as a baseline. Averages are summarized per condition and the best condition per cell line is listed. It also compares every cell line to the U2-OS control. |
| 1    | [`1.boxplots.ipynb`](./1.boxplots.ipynb)                         | [`scripts/1.boxplots.r`](./scripts/1.boxplots.r)                      | Boxplots (R) of the correlation per seeding density, split by shuffled versus unshuffled and by time point, one per cell line.                                                                                                                   |
| 2    | [`2.final-plot.ipynb`](./2.final-plot.ipynb)                     | [`scripts/2.final-plot.py`](./scripts/2.final-plot.py)                | Merges the average correlation with the single-cell QC report (percentage of failing cells) and plots one scatter per cell line: higher correlation and lower failing percentage are better.                                                  |

The scripts in [`scripts/`](./scripts/) are the notebooks converted to Python and R.

## Results

| File                                                                                              | Description                                                                                         |
| :------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------- |
| [`results/all_cell_lines_boxplots.pdf`](./results/all_cell_lines_boxplots.pdf)                      | The boxplots from step 1, one page per cell line.                                                   |
| [`results/rounds_1-4_pearson_vs_percentage_failing_cells.pdf`](./results/rounds_1-4_pearson_vs_percentage_failing_cells.pdf) | The final figure across Rounds 1 to 4: correlation against the percentage of failing cells per cell line. |
| [`pearson_vs_percentage_failing_cells.pdf`](./pearson_vs_percentage_failing_cells.pdf)              | An earlier version of the final figure.                                                             |

## Inputs and environments

- **Input:** the feature selected bulk profiles (`*_bulk_feature_selected.parquet`) and the QC report from the [preprocessing module](../3.preprocessing_features/).
- **Environments:** steps 0 and 2 use the [optimization environment](../environments/optimization_env.yml) (which installs [`pairwise_compare`](https://github.com/WayScience/pairwise_compare)), and step 1 uses the [R environment](../environments/r_environment.yml).
