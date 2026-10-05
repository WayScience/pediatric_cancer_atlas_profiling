#!/bin/bash

# Create the cell line figures: the body figure, the cancer type sunburst, and the sex and age figure.
# Requires pccma_cell_line_metadata.csv (created by build_pccma_cell_line_metadata.ipynb) in this folder, and the
# gganatogram R package, which is not on conda-forge or CRAN (see the note in environments/r_environment.yml).
#
# Usage:
#   bash create_cell_line_figures.bash
# To use a differently named conda environment, set R_ENV, e.g.:
#   R_ENV=my_r_env bash create_cell_line_figures.bash

# stop at the first error, including a failed conda hook or activation (so the figures are never made in the wrong environment)
set -eo pipefail

# make "conda activate" work in this (non-interactive) shell
eval "$(conda shell.bash hook)"
# activate the R-based environment
conda activate "${R_ENV:-alsf_r_analysis}"
set -u   # after activation: conda's own activation scripts use unset variables

# the notebooks use paths relative to their own folder
cd "$(dirname "$0")/notebooks"

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# run each script to create its figures (png and pdf) in the figures folder
for script in nbconverted/*.r; do
    echo "Running ${script}"
    Rscript "${script}"
done

# drawing the plots to the screen device writes Rplots.pdf, which is not needed
rm -f Rplots.pdf

echo "Figures are in $(pwd)/figures"
