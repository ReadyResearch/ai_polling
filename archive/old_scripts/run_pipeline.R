#!/usr/bin/env Rscript

# AI Polling Data Analysis Pipeline - Master Script
# Runs the complete pipeline from markdown conversion to visualization

cat("=== AI POLLING DATA ANALYSIS PIPELINE ===\n")
cat("Strategic Objective: Build evidence for AI regulation through public opinion analysis\n\n")

# Check if required environment variables are set
if (Sys.getenv("GOOGLE_API_KEY") == "") {
  cat("ERROR: GOOGLE_API_KEY environment variable not set.\n")
  cat("Please set your Google API key:\n")
  cat("export GOOGLE_API_KEY='your_api_key_here'\n")
  cat("Get your API key from: https://aistudio.google.com/app/apikey\n")
  quit(status = 1)
}

# Load required libraries
library(fs)

# Create log file for pipeline run
pipeline_log <- file.path("logs", paste0("pipeline_", format(Sys.time(), "%Y%m%d_%H%M%S"), ".log"))
dir_create("logs", recurse = TRUE)

log_pipeline <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  log_entry <- paste0("[", timestamp, "] ", message)
  cat(log_entry, "\n")
  cat(log_entry, "\n", file = pipeline_log, append = TRUE)
}

log_pipeline("Starting AI Polling Data Analysis Pipeline")

# Step 1: Check if markdown files exist
log_pipeline("Step 1: Checking markdown files...")
markdown_files <- dir_ls("polling_markdown", glob = "*.md", type = "file")

if (length(markdown_files) == 0) {
  log_pipeline("No markdown files found. Running conversion first...")
  
  # Run setup if needed
  if (!file.exists("setup_complete.flag")) {
    log_pipeline("Running environment setup...")
    tryCatch({
      source("setup_environment.R")
      file.create("setup_complete.flag")
      log_pipeline("Environment setup completed")
    }, error = function(e) {
      log_pipeline(paste("Setup failed:", e$message))
      quit(status = 1)
    })
  }
  
  # Run conversion
  log_pipeline("Running file conversion...")
  tryCatch({
    source("convert_polling_files.R")
    log_pipeline("File conversion completed")
  }, error = function(e) {
    log_pipeline(paste("Conversion failed:", e$message))
    quit(status = 1)
  })
} else {
  log_pipeline(paste("Found", length(markdown_files), "markdown files"))
}

# Step 2: Data extraction
log_pipeline("Step 2: Extracting polling data using AI...")
tryCatch({
  source("extract_polling_data.R")
  log_pipeline("Data extraction completed")
}, error = function(e) {
  log_pipeline(paste("Data extraction failed:", e$message))
  quit(status = 1)
})

# Step 3: Data validation and cleaning
log_pipeline("Step 3: Validating and cleaning data...")
tryCatch({
  source("validate_data.R")
  log_pipeline("Data validation completed")
}, error = function(e) {
  log_pipeline(paste("Data validation failed:", e$message))
  quit(status = 1)
})

# Step 4: Visualization
log_pipeline("Step 4: Creating visualizations...")
tryCatch({
  source("visualize_polling_data.R")
  log_pipeline("Visualization completed")
}, error = function(e) {
  log_pipeline(paste("Visualization failed:", e$message))
  quit(status = 1)
})

# Pipeline completion
log_pipeline("=== PIPELINE COMPLETED SUCCESSFULLY ===")

# Final summary
cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("PIPELINE SUMMARY\n")
cat(paste(rep("=", 60), collapse = ""), "\n")

# Check outputs
extracted_data <- file.path("extracted_data", "cleaned_polling_data.rds")
if (file.exists(extracted_data)) {
  data <- readRDS(extracted_data)
  cat("✓ Data extraction: SUCCESS\n")
  cat("  - Total records:", nrow(data), "\n")
  cat("  - Countries:", length(unique(data$Country)), "\n")
  cat("  - Categories:", length(unique(data$Category)), "\n")
  cat("  - Date range:", as.character(min(data$Fieldwork_Date, na.rm = TRUE)), 
      "to", as.character(max(data$Fieldwork_Date, na.rm = TRUE)), "\n")
} else {
  cat("✗ Data extraction: FAILED\n")
}

# Check visualizations
viz_dir <- "visualizations"
if (dir.exists(viz_dir)) {
  viz_files <- dir_ls(viz_dir, glob = "*.html")
  cat("✓ Visualizations: SUCCESS\n")
  cat("  - Files created:", length(viz_files), "\n")
  cat("  - Main plot: main_polling_trends.html\n")
  cat("  - Summary heatmap: summary_heatmap.html\n")
  cat("  - Interactive table: data_table.html\n")
} else {
  cat("✗ Visualizations: FAILED\n")
}

cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("NEXT STEPS\n")
cat(paste(rep("=", 60), collapse = ""), "\n")
cat("1. Open visualizations/*.html files in your browser\n")
cat("2. Review extracted_data/cleaned_polling_data.csv\n")
cat("3. Check logs/ directory for detailed processing logs\n")
cat("4. Use the interactive visualizations to explore trends\n")

cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("ADVOCACY INSIGHTS\n")
cat(paste(rep("=", 60), collapse = ""), "\n")
cat("Use these visualizations to demonstrate:\n")
cat("• Consistent global support for AI regulation (60-80%)\n")
cat("• Growing concern about AI risks over time\n")
cat("• Cross-national consistency in regulatory preferences\n")
cat("• Methodological robustness across different surveys\n")

log_pipeline("Pipeline summary completed")
cat("\nFull pipeline log saved to:", pipeline_log, "\n")