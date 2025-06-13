#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# run Python scripts to create LoadData CSVs and perform segmentation + feature extraction with CellProfiler
python nbconverted/0.create_loaddata_csvs.py
python nbconverted/1.cp_analysis_local.py
