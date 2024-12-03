#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# MAKE SURE TO RUN LOADDATA CSV NOTEBOOK IN JUPYTER NOTEBOOK PRIOR TO RUNNING IC DUE TO ERROR IN PYTHON SCRIPT

# run Python script perform segmentation and feature extraction with CellProfiler
python nbconverted/1.cp_analysis.py
