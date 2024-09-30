#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the R-based environment
conda activate alsf_r_analysis

# convert all notebooks to script files into the scripts folder
jupyter nbconvert --to script --output-dir=scripts/ *.ipynb

# run the R script to generate platemap layout figure(s)
Rscript scripts/platemap_fig.r
