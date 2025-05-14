#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=6 # number of cores (plates)
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --account=amc-general
#SBATCH --time=6-00:00 (days-hours:min:sec) # estimate time 6 days-ish (local took 5 days)
#SBATCH --output=run_CP_pwease-%j.out

module load anaconda
conda init bash
# activate the CellProfiler environment
conda activate alsf_cp_env

jupyter nbconvert --to=script --FilesWriter.build_directory=nbconverted/ notebooks/*.ipynb

cd nbconverted/ || exit

python my_script.py

cd ../ || exit
conda deactivate

echo "CP complete!"
