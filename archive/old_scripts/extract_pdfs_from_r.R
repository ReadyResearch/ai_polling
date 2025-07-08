#!/usr/bin/env Rscript

# R wrapper for PDF extraction using Python and reticulate
library(reticulate)
library(tidyverse)

# Source configuration
source("config.R")

extract_pdfs_with_python <- function(pdf_dir = "polling_pdfs", max_files = NULL) {
  
  cat("=== PDF EXTRACTION WITH GEMINI 2.5 FLASH ===\n")
  
  # Ensure API key is available
  if (GOOGLE_API_KEY == "") {
    stop("GOOGLE_API_KEY not available. Please check config.R")
  }
  
  cat("✓ API key loaded (length:", nchar(GOOGLE_API_KEY), "characters)\n")
  
  # Set environment variable for Python
  Sys.setenv(GOOGLE_API_KEY = GOOGLE_API_KEY)
  
  # Source the Python script
  tryCatch({
    source_python("extract_polling_data_pdf_fixed.py")
    cat("✓ Python script loaded successfully\n")
  }, error = function(e) {
    cat("✗ Error loading Python script:", e$message, "\n")
    stop("Failed to load Python script")
  })
  
  # Initialize the extractor
  tryCatch({
    extractor <- PDFPollingExtractor(api_key = GOOGLE_API_KEY, cache_dir = "pdf_cache")
    cat("✓ PDF extractor initialized\n")
  }, error = function(e) {
    cat("✗ Error initializing extractor:", e$message, "\n")
    stop("Failed to initialize PDF extractor")
  })
  
  # Get list of PDF files
  pdf_files <- list.files(pdf_dir, pattern = "\\.pdf$", full.names = TRUE)
  
  if (length(pdf_files) == 0) {
    cat("✗ No PDF files found in", pdf_dir, "\n")
    return(data.frame())
  }
  
  # Limit files if specified
  if (!is.null(max_files) && max_files < length(pdf_files)) {
    pdf_files <- pdf_files[1:max_files]
    cat("📄 Processing first", max_files, "of", length(list.files(pdf_dir, pattern = "\\.pdf$")), "PDF files\n")
  } else {
    cat("📄 Processing", length(pdf_files), "PDF files\n")
  }
  
  # Extract data from each PDF
  all_data <- list()
  
  for (i in seq_along(pdf_files)) {
    pdf_file <- pdf_files[i]
    file_name <- basename(pdf_file)
    
    cat(sprintf("[%d/%d] Processing: %s\n", i, length(pdf_files), file_name))
    
    tryCatch({
      # Extract data from this PDF
      extracted_data <- extractor$extract_from_pdf(pdf_file)
      
      if (length(extracted_data) > 0) {
        # Convert Python list to R data frame
        df <- py_to_r(extracted_data) %>%
          bind_rows()
        
        all_data[[file_name]] <- df
        cat("   ✓ Extracted", nrow(df), "records\n")
      } else {
        cat("   ⚠ No data extracted\n")
      }
      
    }, error = function(e) {
      cat("   ✗ Error:", e$message, "\n")
    })
    
    # Rate limiting
    if (i %% 3 == 0 && i < length(pdf_files)) {
      cat("   ⏱ Pausing briefly...\n")
      Sys.sleep(2)
    }
  }
  
  # Combine all data
  if (length(all_data) > 0) {
    combined_df <- bind_rows(all_data, .id = "source_file")
    
    # Clean up data types
    combined_df <- combined_df %>%
      mutate(
        Fieldwork_Date = as.Date(Fieldwork_Date),
        Agreement = as.numeric(Agreement),
        Neutral = as.numeric(Neutral),
        Disagreement = as.numeric(Disagreement),
        N_Respondents = as.numeric(N_Respondents)
      )
    
    cat("\n=== EXTRACTION RESULTS ===\n")
    cat("Total records:", nrow(combined_df), "\n")
    cat("Files processed:", length(all_data), "\n")
    cat("Organizations:", paste(unique(combined_df$Survey_Organisation), collapse = ", "), "\n")
    cat("Countries:", length(unique(combined_df$Country)), "\n")
    cat("Categories:", paste(unique(combined_df$Category), collapse = ", "), "\n")
    
    # AI Regulation summary
    ai_reg <- combined_df %>% filter(Category == "AI_Regulation")
    cat("\n=== AI_REGULATION SUMMARY ===\n")
    cat("AI_Regulation records:", nrow(ai_reg), "\n")
    if (nrow(ai_reg) > 0) {
      ai_reg_orgs <- ai_reg %>% 
        count(Survey_Organisation, name = "count") %>%
        arrange(desc(count))
      
      cat("Organizations with AI_Regulation questions:\n")
      for (i in 1:nrow(ai_reg_orgs)) {
        cat("  -", ai_reg_orgs$Survey_Organisation[i], ":", ai_reg_orgs$count[i], "questions\n")
      }
    }
    
    # Save results
    output_dir <- "extracted_data"
    if (!dir.exists(output_dir)) dir.create(output_dir)
    
    timestamp <- format(Sys.time(), "%Y%m%d_%H%M%S")
    
    # Save as RDS and CSV
    rds_file <- file.path(output_dir, paste0("pdf_extracted_", timestamp, ".rds"))
    csv_file <- file.path(output_dir, paste0("pdf_extracted_", timestamp, ".csv"))
    
    saveRDS(combined_df, rds_file)
    write_csv(combined_df, csv_file)
    
    # Also save as latest
    saveRDS(combined_df, file.path(output_dir, "pdf_extracted_latest.rds"))
    write_csv(combined_df, file.path(output_dir, "pdf_extracted_latest.csv"))
    
    cat("\n💾 Results saved:\n")
    cat("  -", rds_file, "\n")
    cat("  -", csv_file, "\n")
    
    return(combined_df)
    
  } else {
    cat("✗ No data extracted from any files\n")
    return(data.frame())
  }
}

# Function to combine with existing data
combine_with_existing <- function(new_data) {
  
  existing_file <- "extracted_data/combined_polling_data.rds"
  
  if (file.exists(existing_file)) {
    existing_data <- readRDS(existing_file)
    cat("Loaded", nrow(existing_data), "existing records\n")
    
    # Combine datasets
    combined <- bind_rows(existing_data, new_data)
    
    # Remove duplicates based on key fields
    combined <- combined %>%
      distinct(Question_Text, Country, Survey_Organisation, Fieldwork_Date, .keep_all = TRUE)
    
    cat("Combined dataset:", nrow(combined), "records (", nrow(combined) - nrow(existing_data), "new)\n")
    
    # Save enhanced dataset
    saveRDS(combined, "extracted_data/enhanced_polling_data.rds")
    write_csv(combined, "extracted_data/enhanced_polling_data.csv")
    
    return(combined)
  } else {
    cat("No existing data found, using PDF extraction results only\n")
    saveRDS(new_data, "extracted_data/enhanced_polling_data.rds") 
    write_csv(new_data, "extracted_data/enhanced_polling_data.csv")
    return(new_data)
  }
}

# Main execution (if run as script)
if (!interactive()) {
  
  # Extract from PDFs (start with first 5 files for testing)
  pdf_data <- extract_pdfs_with_python(max_files = 5)
  
  if (nrow(pdf_data) > 0) {
    # Combine with existing data
    final_data <- combine_with_existing(pdf_data)
    
    cat("\n=== FINAL DATASET SUMMARY ===\n")
    cat("Total records:", nrow(final_data), "\n")
    
    # Show AI regulation coverage
    ai_reg_final <- final_data %>% filter(Category == "AI_Regulation")
    cat("AI_Regulation records:", nrow(ai_reg_final), "\n")
    
    if (nrow(ai_reg_final) > 0) {
      ai_reg_summary <- ai_reg_final %>%
        count(Survey_Organisation, name = "count") %>%
        arrange(desc(count))
      
      cat("Organizations with AI_Regulation questions:\n")
      for (i in 1:nrow(ai_reg_summary)) {
        cat("  -", ai_reg_summary$Survey_Organisation[i], ":", ai_reg_summary$count[i], "questions\n")
      }
    }
  }
}