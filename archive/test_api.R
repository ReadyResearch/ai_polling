#!/usr/bin/env Rscript

# Test script to debug API calls

library(ellmer)
library(tidyverse)

# Configuration  
source("config.R")

# Test the API connection
cat("Testing Gemini API connection...\n")

# Create chat
chat <- chat_google_gemini(
  model = EXTRACTION_MODEL,
  system_prompt = "You are a helpful assistant. Always respond with valid JSON."
)

# Simple test
test_prompt <- 'Please return a simple JSON array with one test object:
[
  {
    "test": "hello",
    "number": 123
  }
]'

cat("Making test API call...\n")

tryCatch({
  response <- chat$chat(test_prompt, echo = FALSE)
  cat("Response received:\n")
  cat("Length:", nchar(response), "\n")
  cat("Content:\n")
  cat(response)
  cat("\n\n")
  
  # Try to extract JSON from code blocks
  clean_response <- response
  if (grepl("```json", response)) {
    # Split by lines and find json boundaries
    lines <- strsplit(response, "\n")[[1]]
    start_idx <- which(grepl("```json", lines)) + 1
    end_idx <- which(grepl("^```$", lines))
    
    if (length(start_idx) > 0 && length(end_idx) > 0) {
      json_lines <- lines[start_idx:(end_idx - 1)]
      clean_response <- paste(json_lines, collapse = "\n")
      cat("Extracted JSON from code block\n")
    }
  }
  
  cat("Clean response:\n")
  cat(clean_response)
  cat("\n\n")
  
  # Try to parse as JSON
  json_data <- jsonlite::fromJSON(clean_response)
  cat("JSON parsing successful!\n")
  print(json_data)
  
}, error = function(e) {
  cat("Error:", e$message, "\n")
})

cat("\nTest complete.\n")