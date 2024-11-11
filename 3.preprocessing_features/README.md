# Preprocessing morphology features

In this module, we perform preprocessing of the features extracted from CellProfiler using CytoTable (format SQLite output as parquet merged single-cells), coSMicQC (single-cell quality control), and pycytominer (annotation, aggregation, normalize, and feature selection).

It took approximately **5 hours** to preprocess the data across all of the notebooks.
We are using a Linux-based machine running Pop_OS! LTS 22.04 with an AMD Ryzen 7 3700X 8-Core Processor with 16 CPUs and 125 GB of MEM.

## Perform preprocessing

You can perform the preprocessing of morphology features using the command below:

```bash
# Make sure you are in the 3.preprocessing_features directory
source run_preprocessing.sh
```
