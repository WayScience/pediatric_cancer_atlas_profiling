#!/bin/bash

# initialize the correct shell for your machine to allow conda to work (see README for note on shell names)
conda init bash
# activate the preprocessing environment
conda activate alsf_preprocessing_env

# convert all notebooks to script files into the nbconverted folder
jupyter nbconvert --to script --output-dir=nbconverted/ *.ipynb

# first, run CytoTable to generate merged single-cell profiles
python nbconverted/0.convert_cytotable.py

# Define the path to the parent folder to generate list of plate IDs
PARENT_FOLDER="/home/jenna/pediatric_cancer_atlas_profiling/2.feature_extraction/sqlite_outputs/"

# Create an array of folder names (excluding files)
plates=($(find "$PARENT_FOLDER" -mindepth 1 -maxdepth 1 -type d -exec basename {} \;))

# Print the count of folders
echo "Number of plates found: ${#plates[@]}"

# Print the plate names
echo "Plates:"
for plate in "${plates[@]}"; do
    echo "- $plate"
done

# Using papermill, run single cell quality control on all plates
for plate in "${plates[@]}"; do
    papermill \
    1.sc_quality_control.ipynb \
    1.sc_quality_control.ipynb \
    -p plate_id $plate
done

# Run the rest of the preprocessing and reporting
python nbconverted/2.bulk_processing.py
python nbconverted/3.single_cell_processing.py
python nbconverted/3.single_cell_processing.py
