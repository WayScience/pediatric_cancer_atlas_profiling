#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=10G
#SBATCH --partition=amilan
#SBATCH --qos=long
#SBATCH --account=amc-general
#SBATCH --time=4-00:00:00
#SBATCH --output=run_CP_child-%j.out

# 1 task at 10GB RAM for the core (adjust as needed)

# activate cellprofiler environment
module load miniforge
conda init bash
conda activate alsf_cp_env

# input csv  passed as first argument
csv=$1

# convert notebooks to python scripts
jupyter nbconvert --to=script --FilesWriter.build_directory=nbconverted/ *.ipynb

# run your python analysis script with the input csv
python nbconverted/1.cp_analysis_hpc.py --input_csv "$csv"

# deactivate conda environment
conda deactivate

echo "CellProfiler analysis done for directory: $csv"
