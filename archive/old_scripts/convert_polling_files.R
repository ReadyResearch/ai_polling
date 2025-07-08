#!/usr/bin/env Rscript

# AI Polling Data Conversion Pipeline
# Converts PDF and HTML files to markdown for analysis

library(reticulate)
library(fs)
library(stringr)
library(purrr)

# Set up Python environment and import PyMuPDF4LLM
py_config()
pymupdf4llm <- import("pymupdf4llm")

# Define directories
input_dir <- "polling_pdfs"
output_dir <- "polling_markdown"

# Ensure output directory exists
dir_create(output_dir, recurse = TRUE)

# Function to convert PDF to markdown
convert_pdf_to_markdown <- function(pdf_path, output_path) {
  cat("Converting PDF:", pdf_path, "\n")
  
  tryCatch({
    # Use PyMuPDF4LLM to convert PDF to markdown
    md_text <- pymupdf4llm$to_markdown(pdf_path)
    
    # Write to output file
    writeLines(md_text, output_path)
    
    cat("✓ Successfully converted:", pdf_path, "->", output_path, "\n")
    return(TRUE)
    
  }, error = function(e) {
    cat("✗ Error converting", pdf_path, ":", e$message, "\n")
    return(FALSE)
  })
}

# Function to convert HTML to markdown
convert_html_to_markdown <- function(html_path, output_path) {
  cat("Converting HTML:", html_path, "\n")
  
  tryCatch({
    # Load required libraries for HTML processing
    library(rvest)
    library(xml2)
    
    # Read and parse HTML
    html_doc <- read_html(html_path)
    
    # Extract text content (basic conversion)
    # Remove script and style elements
    xml_remove(xml_find_all(html_doc, "//script"))
    xml_remove(xml_find_all(html_doc, "//style"))
    
    # Extract text
    text_content <- html_text(html_doc)
    
    # Clean up whitespace
    text_content <- str_replace_all(text_content, "\\s+", " ")
    text_content <- str_replace_all(text_content, "\\n\\s+", "\n")
    
    # Write to output file
    writeLines(text_content, output_path)
    
    cat("✓ Successfully converted:", html_path, "->", output_path, "\n")
    return(TRUE)
    
  }, error = function(e) {
    cat("✗ Error converting", html_path, ":", e$message, "\n")
    cat("Falling back to raw HTML copy...\n")
    
    # Fallback: copy HTML as-is
    html_content <- readLines(html_path, warn = FALSE)
    writeLines(html_content, output_path)
    return(TRUE)
  })
}

# Get all files in input directory
all_files <- dir_ls(input_dir, type = "file")

# Process each file
conversion_results <- map_lgl(all_files, function(file_path) {
  # Get file extension
  ext <- tools::file_ext(file_path)
  
  # Generate output filename
  base_name <- tools::file_path_sans_ext(basename(file_path))
  output_file <- file.path(output_dir, paste0(base_name, ".md"))
  
  # Convert based on file type
  if (tolower(ext) == "pdf") {
    convert_pdf_to_markdown(file_path, output_file)
  } else if (tolower(ext) == "html") {
    convert_html_to_markdown(file_path, output_file)
  } else {
    cat("⚠ Unsupported file type:", ext, "for file:", file_path, "\n")
    return(FALSE)
  }
})

# Summary
total_files <- length(all_files)
successful_conversions <- sum(conversion_results)

cat("\n", paste(rep("=", 50), collapse = ""), "\n")
cat("CONVERSION SUMMARY\n")
cat(paste(rep("=", 50), collapse = ""), "\n")
cat("Total files processed:", total_files, "\n")
cat("Successful conversions:", successful_conversions, "\n")
cat("Failed conversions:", total_files - successful_conversions, "\n")
cat("Output directory:", output_dir, "\n")
cat(paste(rep("=", 50), collapse = ""), "\n")

# List converted files
converted_files <- dir_ls(output_dir, type = "file")
cat("\nConverted files:\n")
walk(converted_files, ~ cat("  -", basename(.x), "\n"))