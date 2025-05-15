#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --partition=amilan
#SBATCH --qos=normal
#SBATCH --account=amc-general
#SBATCH --time=2:00:00
#SBATCH --output=envs-%j.out

# Adapted from Mike Lippincott's script in NF1_3D_organoid_profiling_pipeline repository on GitHub

module load miniforge

yaml_files=$(ls *.yml)

# read the first line of the yaml file
for yaml_file in $yaml_files; do
    # read the first line of the yaml file
    first_line=$(head -n 1 $yaml_file)
    # parse the first line to get the environment name
    environment_name=$(echo $first_line | cut -d ' ' -f 2)
    # check if the environment exists
    if conda env list | grep -q $environment_name; then
        mamba env update -f $yaml_file
    else
        mamba env create -f $yaml_file
    fi
done

echo "Environments created"
