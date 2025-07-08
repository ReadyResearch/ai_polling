#!/usr/bin/env Rscript

# Combine extracted data files into single dataset

library(tidyverse)
library(fs)

# Find all extracted data files
extracted_files <- dir_ls("extracted_data", glob = "*_data.rds", type = "file")

cat("Found", length(extracted_files), "extracted data files:\n")
for (file in extracted_files) {
  cat("  -", basename(file), "\n")
}

# Load and combine all data
all_data <- map_dfr(extracted_files, readRDS)

cat("\n=== COMBINED DATA SUMMARY ===\n")
cat("Total records:", nrow(all_data), "\n")
cat("Total fields:", ncol(all_data), "\n")
cat("Source files:", length(unique(all_data$source_file)), "\n")

if (nrow(all_data) > 0) {
  cat("\nField names:\n")
  cat(paste(names(all_data), collapse = ", "), "\n")
  
  cat("\nFirst few records:\n")
  print(head(all_data, 3))
  
  # Save combined data
  saveRDS(all_data, "extracted_data/all_polling_data.rds")
  write_csv(all_data, "extracted_data/all_polling_data.csv")
  
  cat("\nCombined data saved to:\n")
  cat("  - extracted_data/all_polling_data.rds\n")
  cat("  - extracted_data/all_polling_data.csv\n")
} else {
  cat("No data found!\n")
}