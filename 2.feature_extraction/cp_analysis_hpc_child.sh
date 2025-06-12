#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=6
#SBATCH --mem-per-cpu=5G
#SBATCH --partition=amilan
#SBATCH --qos=long
#SBATCH --account=amc-general
#SBATCH --time=6-00:00:00
#SBATCH --output=run_CP_child-%j.out

# 6 tasks at 5 GB RAM per core (adjust as needed)

# activate cellprofiler environment
module load anaconda
conda init bash
conda activate alsf_cp_env

# input directory passed as first argument
dir=$1

# convert notebooks to python scripts
jupyter nbconvert --to=script --FilesWriter.build_directory=nbconverted/ *.ipynb

cd nbconverted/ || exit 1

# Create the LoadData CSVs that will be used for running the CellProfiler pipeline
python nbconverted/0.create_loaddata_csvs.py --HPC

# run your python analysis script with the input directory
python 1.cp_analysis_hpc.py --input_dir "$dir"

cd .. || exit 1

# deactivate conda environment
conda deactivate

echo "CellProfiler analysis done for directory: $dir"
