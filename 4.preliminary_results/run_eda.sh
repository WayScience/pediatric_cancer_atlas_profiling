#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the preprocessing environment
conda activate alsf_preprocessing_env

# convert Jupyter notebooks to scripts
jupyter nbconvert --to script --output-dir=scripts/ *.ipynb

# run Python scripts to perform preliminary exploratory analysis
python scripts/0.UMAP_embeddings.py
