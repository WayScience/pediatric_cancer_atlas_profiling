#!/usr/bin/env r
# coding: utf-8

# In[1]:


# Load necessary libraries
library(ggplot2)
library(dplyr)
library(arrow)


# In[2]:


# Set the file path to your results folder
file_dir <- file.path("results")

compare_file <- file.path(file_dir, "pairwise_compare.parquet")

# Process dataset using arrow
df <- arrow::read_parquet(
    compare_file
)


# In[3]:


# Check for duplicate column names (optional debugging step)
print(colnames(df))
seeding_density = unique(df$Metadata_seeding_density__antehoc_group0)


# In[4]:


# Ensure seeding density is treated as a categorical variable
df$Metadata_seeding_density__antehoc_group0 <- as.factor(df$Metadata_seeding_density__antehoc_group0)

# Open PDF for boxplots
pdf("results/all_cell_lines_boxplots.pdf", width = 10, height = 8)

# Loop through each unique cell line
for (cell_line in unique(df$Metadata_cell_line__antehoc_group0)) {
  # Filter data for the current cell line
  cell_line_data <- df %>% filter(Metadata_cell_line__antehoc_group0 == cell_line)
  
  # Create a column to distinguish between shuffled and unshuffled data
  cell_line_data$Shuffled <- ifelse(cell_line_data$Shuffled__antehoc_group0, "Shuffled", "Unshuffled")
  
  # Ensure the order of the Shuffled levels
  cell_line_data$Shuffled <- factor(cell_line_data$Shuffled, levels = c("Unshuffled", "Shuffled"))
  
  # Create the plot
  p_boxplot <- ggplot(cell_line_data, aes(x = Metadata_seeding_density__antehoc_group0, y = pearsons_correlation)) +
    geom_boxplot() +
    facet_grid(Shuffled ~ Metadata_time_point__antehoc_group0, scales = "fixed") +
    labs(
      title = paste("Cell Line:", cell_line),
      x = "Seeding Density",
      y = "Pearson's Correlation"
    )
  
  # Save the plot to a PNG file
  output_file <- paste0("results/", cell_line, "_boxplot.png")
  ggsave(output_file, plot = p_boxplot, width = 10, height = 8)
  # Print the boxplot into the PDF
  print(p_boxplot)
}

# Close the PDF for boxplots
dev.off()
