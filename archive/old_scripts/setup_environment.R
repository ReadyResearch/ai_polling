#!/usr/bin/env Rscript

# Environment Setup for AI Polling Data Conversion
# Installs required packages and sets up Python environment

cat("Setting up environment for AI polling data conversion...\n")

# Required R packages
required_packages <- c(
  "reticulate",
  "fs",
  "stringr",
  "purrr",
  "rvest",
  "xml2",
  "ellmer",
  "tidyverse",
  "lubridate",
  "jsonlite",
  "digest",
  "plotly",
  "htmlwidgets",
  "DT",
  "RColorBrewer"
)

# Install missing packages
missing_packages <- required_packages[!required_packages %in% installed.packages()[,"Package"]]

if (length(missing_packages) > 0) {
  cat("Installing missing R packages:", paste(missing_packages, collapse = ", "), "\n")
  install.packages(missing_packages, dependencies = TRUE)
}

# Load reticulate to set up Python
library(reticulate)

# Check if pymupdf4llm is available
tryCatch({
  pymupdf4llm <- import("pymupdf4llm")
  cat("✓ PyMuPDF4LLM is available\n")
}, error = function(e) {
  cat("⚠ PyMuPDF4LLM not found. Installing...\n")
  py_install("pymupdf4llm", pip = TRUE)
  cat("✓ PyMuPDF4LLM installed\n")
})

# Check Python environment
cat("Python executable:", py_config()$python, "\n")
cat("Python version:", as.character(py_config()$version), "\n")

cat("✓ Environment setup complete!\n")

