suppressPackageStartupMessages(library(dplyr))
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(platetools))

# Define the path to the platemaps folder
platemaps_folder <- "platemaps"

# Set up the file naming pattern for the platemap files (CSVs)
platemap_files <- list.files(path = platemaps_folder, pattern = "_platemap\\.csv$", full.names = TRUE)
print(platemap_files)

# Set output directory for the layout figures
output_fig_dir <- file.path("platemap_figures")

# Create the directory if it doesn't exist, ignore if it already exists
dir.create(output_fig_dir, showWarnings = FALSE, recursive = TRUE)

# Set suffix for output figures
platemap_suffix <- "_platemap_figure.png"

# Instantiate empty list for the plate layout names + output paths 
output_platemap_files <- list()

# Extract plate name and add output path for figure
for (platemap_file in platemap_files) {
    # Extract the base file name
    plate <- basename(platemap_file)
    
    # Remove the '_platemap.csv' suffix
    plate <- stringr::str_remove(plate, "_platemap\\.csv")
    
    # (Optional) Ensure there is no .csv extension remaining (shouldn't be needed after the above line)
    plate <- stringr::str_remove(plate, "\\.csv$")
    
    # Add to output_platemap_files with the cleaned plate name and output path
    output_platemap_files[[plate]] <- file.path(output_fig_dir, paste0(plate, platemap_suffix))
}

print(output_platemap_files)

# Load in all platemap CSV files
platemap_dfs <- list()
for (plate in names(output_platemap_files)) {
    # Find the umap file associated with the plate
    platemap_file <- platemap_files[stringr::str_detect(platemap_files, plate)]
    
    # Load in the umap data
    df <- readr::read_csv(
    platemap_file,
    col_types = readr::cols(.default = "c")
)

    platemap_dfs[[plate]] <- df 
}

print(platemap_dfs)

for (plate in names(platemap_dfs)) {
    # Get the updated plate name
    updated_plate <- gsub("_Plate", " Plate ", plate)

    # output for each plate
    output_file <- output_platemap_files[[plate]]
    output_file <- paste0(output_file)
    
    platemap <- platetools::raw_map(
        data = as.numeric(platemap_dfs[[plate]]$seeding_density),
        well = platemap_dfs[[plate]]$well,
        plate = 384,
        size = 6
        ) +
        ggtitle(paste(updated_plate, "layout based on seeding density")) +
        theme(plot.title = element_text(size = 10, face = "bold")) +
        ggplot2::scale_fill_gradient2(
            name = "Seed Density",
            low = "white",
            high = "red",
        )  

    ggsave(
        output_file,
        platemap,
        dpi = 500,
        height = 3.5,
        width = 6
    )
}
