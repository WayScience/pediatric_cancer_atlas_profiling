# Download data

## Current Access Instructions for Microscopy Images (Development)

**Note:** The current method of accessing and downloading the microscopy image data is intended for development purposes only. 
When the data becomes publicly available, access methods will change, and this README will be updated to reflect the final public access protocol.

### Pre-Requisites and Dependencies
- Access to CU-Boulder Alpine compute cluster.
- Access to PetaLibrary Data storage on the Alpine compute cluster (specifically `/pl/active/koala/`).
- A registered **Globus account** with CU credentials and access to the Globus web interface.
  - *(Optional)* Installation of the `globus-cli` command-line tool for advanced users.
- Globus Connect Personal installed and configured on the local machine for data transfer.
  - Ensure that the local Globus endpoint is properly configured with allowed paths for data transfer.

### Instructions for Data Transfer Using Globus Web Interface
1. Log in to the [Globus web interface](https://app.globus.org/).
2. Select the **File Manager** tab from the left-hand menu.
3. Search for the source and destination endpoints in the search box:
   - Source endpoint: `CU Boulder Research Computing` for Alpine.
   - Destination endpoint: your personal Globus Connect Personal endpoint.
4. Specify the source path (`/pl/active/koala/`) and the destination path on your local machine.
   - Note: You must explicitly configure your Globus Connect Personal installation to allow access to the intended local paths.
5. Select the files to transfer and click **Start Transfer**. You can configure transfer options (e.g., email notifications, concurrency) under **Transfer & Timer Options**.
6. During the transfer, you may need to authorize access to both endpoints using your CU credentials.

### Instructions for Data Transfer Using Globus CLI
1. Log in to the Globus CLI using the command `globus login`.

2. Look up endpoint IDs:
   - For Alpine, use the command `globus endpoint search "CU Boulder Research Computing"`. 
        * As of 01/02/2025, the endpoint ID for Alpine is `4718fe94-aafd-498a-8bae-6bd430bb50a0`.
   - For your local machine, use the command `globus endpoint local-id`.

3. Initiate the transfer:
   - Use the command `globus transfer <source_endpoint_id>:/pl/active/koala/<file_or_dir> <destination_endpoint_id>:/local/path/to/destination`.
   - Replace `<source_endpoint_id>` and `<destination_endpoint_id>` with the appropriate endpoint IDs.
   - Replace `<file_or_dir>` and `/local/path/to/destination` with the specific paths.

4. Confirm the transfer:
   - You may be prompted to authorize the transfer. Follow the on-screen instructions.
   - After initiating the transfer, the console should output:  
     `Message: The transfer has been accepted and a task has been created and queued for execution`  
     `Task ID: xxxxx`

5. Monitor the transfer:
   - Use the command `globus task show <task_id>` to check the status of your transfer.

### Future Access Information
Once the microscopy image data is publicly released, access will no longer require CU credentials or the current development-specific setup.
Instructions for public access, including any associated data repositories, will be added here upon release.

## Metadata and layout figures

The [platemaps](./metadata/platemaps/) describe every pilot plate: which cell line, seeding density, and plating condition is in each well, and which barcode is which layout and time point.
The figures of the layouts are made from the platemaps by a notebook in this module.

### Contents

| Path                                                                               | Description                                                                                                          |
| :--------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------- |
| [`metadata/platemaps/Assay_Plate{1..13}_platemap.csv`](./metadata/platemaps/)                         | One file per plate layout. Columns: `cell_line`, `row`, `column`, `well`, `seeding_density`, `condition`.            |
| [`metadata/platemaps/Barcode_platemap_pilot_data.csv`](./metadata/platemaps/Barcode_platemap_pilot_data.csv) | One row per plate (39): `barcode`, `time_point` (24, 48, or 72 hours), and the `platemap_file` (layout) it uses.     |
| [`platemap_figures/`](./platemap_figures/)                                          | Figures of the layouts, colored by cell line and by seeding density. |
| [`platemap_fig.ipynb`](./platemap_fig.ipynb)                                        | Notebook (R) that draws a layout figure for every `*_platemap.csv`.                                                  |
| [`create_figs.sh`](./create_figs.sh)                                                | Converts the notebook to a script (`nbconverted/platemap_fig.r`) and runs it.                                        |

Only wells that contain cells are listed in the platemaps: any empty portion of a layout contains media and no cells, so it is not included.

### Layouts

Each layout was imaged at three time points, which makes three plates per layout (39 plates in all).
Cell line counts are the number of distinct `cell_line` labels in the platemap.

| Layout          | Round   | Plating condition(s) (`condition`)                                  | Cell lines |
| :-------------- | :------ | :------------------------------------------------------------------ | ---------: |
| `Assay_Plate1`  | Round 1 | `standard`                                                          |         12 |
| `Assay_Plate2`  | Round 1 | `standard`                                                          |          7 |
| `Assay_Plate3`  | Round 2 | `synthemax`                                                         |         13 |
| `Assay_Plate4`  | Round 2 | `synthemax_PFA`                                                     |          5 |
| `Assay_Plate5`  | Round 3 | `synthemax`                                                         |         12 |
| `Assay_Plate6`  | Round 3 | `synthemax`                                                         |          3 |
| `Assay_Plate7`  | Round 3 | `synthemax`                                                         |          8 |
| `Assay_Plate8`  | Round 3 | `synthemax_PFA`                                                     |         12 |
| `Assay_Plate9`  | Round 4 | `synthemax`                                                         |         10 |
| `Assay_Plate10` | Round 4 | `synthemax_PFA`                                                     |         11 |
| `Assay_Plate11` | Round 4 | `synthemax_PFA`                                                     |         11 |
| `Assay_Plate12` | Round 4 | `laminin_PFA`                                                       |          3 |
| `Assay_Plate13` | Round 4 | `laminin`, `laminin_PFA`, `standard`, `standard_PFA`, `synthemax_PFA` |          4 |

Every layout has five seeding densities per cell line (1000, 2000, 4000, 8000, and 12000 cells per well), typically with four replicate wells per cell line, condition, and density.
U2-OS is in all 13 layouts and is used as an anchor to compare profiles across plates.

**NOTE:** Cell line names are not harmonized across platemaps: the same line can appear under different labels (for example `A673` and `A-673`, `SH-SY5Y` and `SHSY5Y`, or `CHP212` and `CHP-212` variants).
Check the labels before grouping by `cell_line` across layouts.

### Regenerating the layout figures

The figures are generated in R, so use the R environment from the [environments](../environments/) folder (`alsf_r_analysis`).

```bash
# Make sure you are in the 0.download_data directory
source create_figs.sh
```

The script draws two figures (by cell line and by seeding density) for every layout in `metadata/platemaps/` and writes them to `platemap_figures/`, which has all 13 layouts.
