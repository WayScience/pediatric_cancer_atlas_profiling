#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# run Python scripts for creating LoadData CSVs, extract QC features with CellProfiler, and performing IC
python nbconverted/0.create_loaddata_csvs.py
python nbconverted/1.extract_image_quality.py
python nbconverted/2.evalute_qc.py
python nbconverted/3.cp_illum_correction.py
