#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# run Python scripts for creating LoadData CSVs
python nbconverted/0.create_loaddata_csvs.py

##### OPTIONAL #######
# Perform QC (comment back in this part if you need to update QC)
# cd img_quality_control

# jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# python nbconverted/0.extract_image_quality.py
# python nbconverted/1.evaluate_qc.py

# Extract IC images to perform correction in CP analysis pipeline
python nbconverted/1.cp_illum_correction.py
