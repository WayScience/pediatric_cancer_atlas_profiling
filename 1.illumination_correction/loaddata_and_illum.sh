#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

# convert Jupyter notebooks to scripts
jupyter nbconvert --to script --output-dir=scripts/ *.ipynb

# MAKE SURE TO RUN LOADDATA CSV NOTEBOOK IN JUPYTER NOTEBOOK PRIOR TO RUNNING IC DUE TO ERROR IN PYTHON SCRIPT

# run Python script calculating IC functions + extract QC features with CellProfiler
python scripts/1.cp_illum_correction.py
