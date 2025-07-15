#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --account=amc-general
#SBATCH --time=10:00
#SBATCH --output=cp_parent-%j.out

# activate cellprofiler environment
module load miniforge
conda init bash
conda activate alsf_cp_env

# convert all notebooks to python scripts (if any exist)
jupyter nbconvert --to=script --FilesWriter.build_directory=nbconverted/ *.ipynb

# run the LoadData CSV creation script once before submitting jobs
python nbconverted/0.create_loaddata_csvs.py --HPC

# define the round variable
round="Round_3_data"

# build the data directory path using the variable
data_dir="./loaddata_csvs/${round}"

# get a list of all LoadData CSV files in the raw data folder
mapfile -t loaddata_csvs < <(find "$data_dir" -type f -name "*_concatenated_with_illum.csv" | sed "s|^|$(pwd)/|")

echo "Number of LoadData CSV files: ${#loaddata_csvs[@]}"

for file in "${loaddata_csvs[@]}"; do
    echo "Found: $file"
done

# loop over each CSV and submit child jobs
for loaddata_file in "${loaddata_csvs[@]}"; do
    # check job count for this user
    number_of_jobs=$(squeue -u "$USER" | wc -l)
    while [ "$number_of_jobs" -gt 990 ]; do
        sleep 1s
        number_of_jobs=$(squeue -u "$USER" | wc -l)
    done
    sbatch cp_analysis_hpc_child.sh "$loaddata_file"
done

conda deactivate

echo "All CellProfiler jobs submitted!"
