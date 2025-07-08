#!/usr/bin/env Rscript

# AI Polling Data Extraction Pipeline
# Extracts structured polling data from markdown files using AI

library(tidyverse)
library(lubridate)
library(fs)
library(jsonlite)
library(ellmer)
library(digest)

# Configuration
source("config.R")

# Create directories
dir_create("cache", recurse = TRUE)
dir_create("extracted_data", recurse = TRUE)
dir_create("logs", recurse = TRUE)

# Initialize logging
log_file <- file.path("logs", paste0("extraction_", format(Sys.time(), "%Y%m%d_%H%M%S"), ".log"))
log_connection <- file(log_file, "a")

# Logging function
log_message <- function(level, message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  log_entry <- paste0("[", timestamp, "] ", level, ": ", message)
  cat(log_entry, "\n", file = log_connection, append = TRUE)
  cat(log_entry, "\n")
}

# Cache management functions
get_cache_path <- function(file_path) {
  cache_key <- digest(file_path, algo = "md5")
  file.path("cache", paste0(cache_key, ".rds"))
}

is_cache_valid <- function(cache_path, original_file, max_age_hours = 24) {
  if (!file.exists(cache_path)) return(FALSE)

  cache_time <- file.info(cache_path)$mtime
  original_time <- file.info(original_file)$mtime

  # Check if cache is newer than original file and not too old
  cache_newer <- cache_time > original_time
  cache_recent <- difftime(Sys.time(), cache_time, units = "hours") < max_age_hours

  return(cache_newer && cache_recent)
}

save_to_cache <- function(data, cache_path) {
  tryCatch({
    cache_data <- list(
      data = data,
      timestamp = Sys.time(),
      version = "1.0"
    )
    saveRDS(cache_data, cache_path)
    log_message("INFO", paste("Saved to cache:", cache_path))
  }, error = function(e) {
    log_message("ERROR", paste("Failed to save cache:", e$message))
  })
}

load_from_cache <- function(cache_path) {
  tryCatch({
    cache_data <- readRDS(cache_path)
    log_message("INFO", paste("Loaded from cache:", cache_path))
    return(cache_data$data)
  }, error = function(e) {
    log_message("ERROR", paste("Failed to load cache:", e$message))
    return(NULL)
  })
}

# Create chat object with system prompt
create_extraction_chat <- function() {
  system_prompt <- '
You are a data extraction specialist. Extract ALL polling questions from documents that meet these criteria:
- Binary questions (Yes/No, Agree/Disagree, Support/Oppose)
- Likert scale questions (3-point, 5-point, 7-point scales)
- Multiple choice questions with clear ordinal responses

For EACH qualifying question, extract:
- Question_Text: Exact wording from survey
- Response_Scale: Exact response options available
- Category: One of [AI_Regulation, AI_Risk_Concern, Job_Displacement, Extinction_Risk, AI_Sentiment, Other]
- Agreement: Sum of positive/supportive response percentages
- Neutral: Percentage for neutral/middle responses (if applicable)
- Disagreement: Sum of negative/opposing response percentages
- N_Respondents: Number of survey respondents
- Country: Country/region where conducted
- Survey_Organisation: Organization that conducted survey
- Fieldwork_Date: When survey was conducted (extract date/month/year)
- Notes: Any methodological details or caveats

Return ONLY a JSON array of objects, one per question-country combination. Include ALL qualifying questions - do not make comparability judgments.
'

  chat_google_gemini(
    model = EXTRACTION_MODEL,
    system_prompt = system_prompt
  )
}

# AI extraction function
extract_polling_data <- function(markdown_content, file_name) {

  extraction_prompt <- paste0(
    'Please extract polling data from this document and return as JSON array:\n\n',
    'Example format:\n',
    '[\n',
    '  {\n',
    '    "Question_Text": "Do you support government regulation of AI?",\n',
    '    "Response_Scale": "Strongly support, Somewhat support, Somewhat oppose, Strongly oppose",\n',
    '    "Category": "AI_Regulation",\n',
    '    "Agreement": 67,\n',
    '    "Neutral": 0,\n',
    '    "Disagreement": 33,\n',
    '    "N_Respondents": 1000,\n',
    '    "Country": "United States",\n',
    '    "Survey_Organisation": "Pew Research Center",\n',
    '    "Fieldwork_Date": "2024-03-15",\n',
    '    "Notes": "Margin of error ±3.1%"\n',
    '  }\n',
    ']\n\n',
    'Document to analyze:\n',
    markdown_content
  )

  # Make API request with retry logic
  max_retries <- MAX_API_RETRIES
  retry_count <- 0

  while (retry_count < max_retries) {
    tryCatch({
      log_message("INFO", paste("Making API request for", file_name, "- attempt", retry_count + 1))

      # Create new chat for each extraction to avoid context buildup
      chat <- create_extraction_chat()

      # Get response
      response <- chat$chat(extraction_prompt, echo = FALSE)

      log_message("INFO", paste("Raw API response length:", nchar(response)))
      log_message("INFO", paste("Response preview:", substr(response, 1, 200), "..."))

      # Clean response - extract JSON from markdown code blocks if present
      clean_response <- response
      if (grepl("```json", response)) {
        # Split by lines and find json boundaries
        lines <- strsplit(response, "\n")[[1]]
        start_idx <- which(grepl("```json", lines)) + 1
        end_idx <- which(grepl("^```$", lines))
        
        if (length(start_idx) > 0 && length(end_idx) > 0) {
          json_lines <- lines[start_idx:(end_idx - 1)]
          clean_response <- paste(json_lines, collapse = "\n")
          log_message("INFO", "Extracted JSON from markdown code block")
        } else {
          clean_response <- response
          log_message("WARN", "Failed to extract from JSON code block, using raw response")
        }
      } else if (grepl("```", response)) {
        # Split by lines and find generic code boundaries
        lines <- strsplit(response, "\n")[[1]]
        start_idx <- which(grepl("^```", lines)) + 1
        end_idx <- which(grepl("^```$", lines))
        
        if (length(start_idx) > 0 && length(end_idx) > 0 && start_idx < end_idx) {
          json_lines <- lines[start_idx:(end_idx - 1)]
          clean_response <- paste(json_lines, collapse = "\n")
          log_message("INFO", "Extracted content from generic code block")
        } else {
          clean_response <- response
          log_message("WARN", "Failed to extract from code block, using raw response")
        }
      } else {
        log_message("INFO", "Using raw response as JSON")
      }

      log_message("INFO", paste("Clean response length:", nchar(clean_response)))
      if (is.na(clean_response) || clean_response == "") {
        log_message("ERROR", "Clean response is empty or NA")
        stop("Empty response after cleaning")
      }

      # Parse JSON response
      extracted_data <- tryCatch({
        temp_data <- fromJSON(clean_response, flatten = TRUE)
        
        # Convert to data frame if it's a list
        if (is.list(temp_data) && !is.data.frame(temp_data)) {
          if (length(temp_data) > 0) {
            bind_rows(temp_data)
          } else {
            data.frame()
          }
        } else if (is.data.frame(temp_data)) {
          temp_data
        } else {
          data.frame()
        }
      }, error = function(e) {
        log_message("ERROR", paste("JSON parsing failed:", e$message))
        log_message("ERROR", paste("Raw response:", substr(clean_response, 1, 500)))
        data.frame()
      })

      # Add metadata
      if (is.data.frame(extracted_data) && nrow(extracted_data) > 0) {
        extracted_data$source_file <- file_name
        extracted_data$extraction_date <- Sys.Date()
      }

      log_message("INFO", paste("Successfully extracted", nrow(extracted_data), "records from", file_name))
      return(extracted_data)

    }, error = function(e) {
      log_message("ERROR", paste("API request error for", file_name, ":", e$message))
      retry_count <- retry_count + 1
      if (retry_count < max_retries) {
        log_message("INFO", paste("Retrying in", 2^retry_count, "seconds..."))
        Sys.sleep(2^retry_count)  # Exponential backoff
      }
    })
  }

  log_message("ERROR", paste("Failed to extract data from", file_name, "after", max_retries, "attempts"))
  return(data.frame())
}

# Main processing function
process_markdown_file <- function(file_path) {
  log_message("INFO", paste("Processing file:", file_path))

  file_name <- basename(file_path)
  cache_path <- get_cache_path(file_path)

  # Check cache first
  if (is_cache_valid(cache_path, file_path)) {
    log_message("INFO", paste("Using cached data for", file_name))
    return(load_from_cache(cache_path))
  }

  # Read markdown file
  tryCatch({
    markdown_content <- read_file(file_path)

    # Check if file is too large (>50KB)
    if (nchar(markdown_content) > 50000) {
      log_message("WARN", paste("Large file detected:", file_name, "- truncating"))
      markdown_content <- substr(markdown_content, 1, 50000)
    }

    # Extract data using AI
    extracted_data <- extract_polling_data(markdown_content, file_name)

    # Save to cache
    save_to_cache(extracted_data, cache_path)

    # Save individual file results
    output_file <- file.path("extracted_data", paste0(tools::file_path_sans_ext(file_name), "_data.rds"))
    saveRDS(extracted_data, output_file)

    return(extracted_data)

  }, error = function(e) {
    log_message("ERROR", paste("Failed to process", file_name, ":", e$message))
    return(data.frame())
  })
}

# Main execution
main <- function() {
  log_message("INFO", "Starting polling data extraction pipeline")

  # Get all markdown files
  markdown_files <- dir_ls("polling_markdown", glob = "*.md", type = "file")

  if (length(markdown_files) == 0) {
    log_message("ERROR", "No markdown files found in polling_markdown directory")
    return()
  }

  log_message("INFO", paste("Found", length(markdown_files), "markdown files to process"))

  # Process each file
  all_extracted_data <- map_dfr(markdown_files, process_markdown_file)

  # Save combined results
  if (nrow(all_extracted_data) > 0) {
    output_file <- file.path("extracted_data", "all_polling_data.rds")
    saveRDS(all_extracted_data, output_file)

    # Also save as CSV for inspection
    csv_file <- file.path("extracted_data", "all_polling_data.csv")
    write_csv(all_extracted_data, csv_file)

    log_message("INFO", paste("Extraction complete. Total records:", nrow(all_extracted_data)))
    log_message("INFO", paste("Data saved to:", output_file))

    # Print summary
    cat("\n=== EXTRACTION SUMMARY ===\n")
    cat("Total records extracted:", nrow(all_extracted_data), "\n")
    cat("Files processed:", length(unique(all_extracted_data$source_file)), "\n")
    cat("Countries covered:", length(unique(all_extracted_data$Country)), "\n")
    cat("Survey organizations:", length(unique(all_extracted_data$Survey_Organisation)), "\n")
    cat("Question categories:\n")
    print(table(all_extracted_data$Category))

  } else {
    log_message("WARN", "No data extracted from any files")
  }
}

# Run main function
if (!interactive()) {
  main()
}

# Close log file
close(log_connection)

