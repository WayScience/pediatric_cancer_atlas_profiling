#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the preprocessing environment
conda activate alsf_preprocessing_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# run Python scripts to perform preprocessing
python nbconverted/0.convert_cytotable.py
python nbconverted/1.sc_quality_control.py
python nbconverted/2.bulk_processing.py
python nbconverted/3.single_cell_processing.py
