#!/usr/bin/env Rscript

library(tidyverse)
library(googlesheets4)

# Load all cached data and combine properly
combine_all_data <- function() {
  
  # Load existing Deltapoll + original data
  existing_data <- readRDS("extracted_data/combined_polling_data.rds")
  
  # Load all new cached extractions
  cache_files <- list.files("cache/", pattern = ".rds", full.names = TRUE)
  
  all_extractions <- list()
  
  for (file in cache_files) {
    data <- readRDS(file)
    
    # Skip if this data is already in existing dataset
    if (nrow(data) > 0 && "Survey_Organisation" %in% names(data)) {
      org <- unique(data$Survey_Organisation)[1]
      
      # Check if this organization is already represented
      if (!org %in% existing_data$Survey_Organisation) {
        all_extractions[[basename(file)]] <- data
        cat("Adding", nrow(data), "records from", org, "\n")
      } else {
        cat("Skipping", org, "- already in dataset\n")
      }
    }
  }
  
  # Combine all new data
  if (length(all_extractions) > 0) {
    new_data <- bind_rows(all_extractions)
    
    # Combine with existing data
    final_data <- bind_rows(existing_data, new_data)
    
    cat("Final dataset:", nrow(final_data), "records\n")
    cat("Organizations:", paste(unique(final_data$Survey_Organisation), collapse = ", "), "\n")
    
    # Save expanded dataset
    saveRDS(final_data, "extracted_data/expanded_polling_data.rds")
    write_csv(final_data, "extracted_data/expanded_polling_data.csv")
    
    return(final_data)
  } else {
    cat("No new data to add, using existing dataset\n")
    write_csv(existing_data, "extracted_data/expanded_polling_data.csv")
    return(existing_data)
  }
}

# Upload to Google Sheets
upload_to_sheets <- function(data) {
  
  # Authenticate with Google Sheets (will prompt for auth if needed)
  gs4_auth()
  
  # The spreadsheet URL provided
  sheet_url <- "https://docs.google.com/spreadsheets/d/1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE/edit?gid=1312672982#gid=1312672982"
  
  # Extract sheet ID from URL
  sheet_id <- "1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE"
  
  # Clear existing data in tab 3 and upload new data
  tryCatch({
    # Clear the existing content first
    range_clear(ss = sheet_id, sheet = 3)
    
    # Write the data to tab 3
    range_write(
      ss = sheet_id,
      data = data,
      sheet = 3,
      range = "A1",
      col_names = TRUE,
      reformat = FALSE
    )
    
    cat("Successfully uploaded", nrow(data), "records to Google Sheet tab 3\n")
    
  }, error = function(e) {
    cat("Error uploading to Google Sheets:", e$message, "\n")
    cat("Data saved locally as 'expanded_polling_data.csv'\n")
  })
}

# Main execution
if (!interactive()) {
  cat("=== EXPANDING POLLING DATASET ===\n")
  
  # Combine all available data
  final_data <- combine_all_data()
  
  # Show summary statistics
  cat("\n=== DATASET SUMMARY ===\n")
  cat("Total records:", nrow(final_data), "\n")
  cat("Date range:", min(final_data$Fieldwork_Date, na.rm = TRUE), "to", max(final_data$Fieldwork_Date, na.rm = TRUE), "\n")
  
  # Show breakdown by category and organization
  cat("\n=== RECORDS BY CATEGORY ===\n")
  category_summary <- final_data %>%
    count(Category, Survey_Organisation) %>%
    arrange(Category, Survey_Organisation)
  
  print(category_summary)
  
  # Show AI_Regulation specifically
  ai_reg <- final_data %>% filter(Category == "AI_Regulation")
  cat("\n=== AI_REGULATION BREAKDOWN ===\n")
  cat("Total AI_Regulation records:", nrow(ai_reg), "\n")
  cat("Organizations with AI_Regulation questions:", paste(unique(ai_reg$Survey_Organisation), collapse = ", "), "\n")
  
  # Upload to Google Sheets
  cat("\n=== UPLOADING TO GOOGLE SHEETS ===\n")
  upload_to_sheets(final_data)
}