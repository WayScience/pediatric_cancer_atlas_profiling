#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=6 # number of cores (plates)
#SBATCH --mem-per-cpu=4.5G
#SBATCH --partition=amilan
#SBATCH --qos=long
#SBATCH --account=amc-general
#SBATCH --time=5-00:00 (days-hours:min:sec) # estimate time for one plate testing
#SBATCH --output=run_CP-%j.out

module load miniforge
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

jupyter nbconvert --to=script --FilesWriter.build_directory=nbconverted/ *.ipynb

cd nbconverted/ || exit

# Create the LoadData CSVs that will be used for running the CellProfiler pipeline
python 0.create_loaddata_csvs.py

# Perform CellProfiler in parallel for the plates
python 1.cp_analysis.py

cd ../ || exit
conda deactivate

echo "CP complete!"
