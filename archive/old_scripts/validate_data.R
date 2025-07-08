#!/usr/bin/env Rscript

# Data Validation and Quality Checks for AI Polling Pipeline

library(tidyverse)
library(lubridate)
library(fs)

source("config.R")

# Validation functions
validate_required_fields <- function(data) {
  missing_fields <- setdiff(REQUIRED_FIELDS, names(data))
  
  if (length(missing_fields) > 0) {
    warning(paste("Missing required fields:", paste(missing_fields, collapse = ", ")))
    return(FALSE)
  }
  
  # Check for empty values in required fields
  empty_counts <- data %>%
    select(all_of(REQUIRED_FIELDS)) %>%
    summarise(across(everything(), ~ sum(is.na(.) | . == ""))) %>%
    pivot_longer(everything(), names_to = "field", values_to = "empty_count") %>%
    filter(empty_count > 0)
  
  if (nrow(empty_counts) > 0) {
    warning("Empty values found in required fields:")
    print(empty_counts)
  }
  
  return(nrow(empty_counts) == 0)
}

validate_categories <- function(data) {
  invalid_categories <- data %>%
    filter(!Category %in% VALID_CATEGORIES) %>%
    pull(Category) %>%
    unique()
  
  if (length(invalid_categories) > 0) {
    warning(paste("Invalid categories found:", paste(invalid_categories, collapse = ", ")))
    return(FALSE)
  }
  
  return(TRUE)
}

validate_percentages <- function(data) {
  # Check Agreement, Neutral, and Disagreement percentages
  percentage_issues <- data %>%
    mutate(
      agreement_valid = Agreement >= MIN_AGREEMENT_PERCENT & Agreement <= MAX_AGREEMENT_PERCENT,
      disagreement_valid = Disagreement >= MIN_AGREEMENT_PERCENT & Disagreement <= MAX_AGREEMENT_PERCENT,
      neutral_valid = is.na(Neutral) | (Neutral >= MIN_AGREEMENT_PERCENT & Neutral <= MAX_AGREEMENT_PERCENT),
      total_valid = is.na(Neutral) | (Agreement + Disagreement + Neutral <= 105)  # Allow 5% tolerance
    ) %>%
    filter(!agreement_valid | !disagreement_valid | !neutral_valid | !total_valid)
  
  if (nrow(percentage_issues) > 0) {
    warning(paste("Found", nrow(percentage_issues), "records with invalid percentages"))
    return(FALSE)
  }
  
  return(TRUE)
}

validate_sample_sizes <- function(data) {
  small_samples <- data %>%
    filter(N_Respondents < MIN_RESPONDENTS) %>%
    nrow()
  
  if (small_samples > 0) {
    warning(paste("Found", small_samples, "records with sample size <", MIN_RESPONDENTS))
  }
  
  return(small_samples == 0)
}

validate_dates <- function(data) {
  # Try to parse dates
  date_issues <- data %>%
    mutate(
      parsed_date = ymd(Fieldwork_Date),
      date_valid = !is.na(parsed_date) & parsed_date >= as.Date("2020-01-01") & parsed_date <= Sys.Date()
    ) %>%
    filter(!date_valid)
  
  if (nrow(date_issues) > 0) {
    warning(paste("Found", nrow(date_issues), "records with invalid dates"))
    return(FALSE)
  }
  
  return(TRUE)
}

# Main validation function
validate_polling_data <- function(data) {
  cat("=== DATA VALIDATION REPORT ===\n")
  cat("Total records:", nrow(data), "\n")
  cat("Total fields:", ncol(data), "\n\n")
  
  validation_results <- list()
  
  # Run all validation checks
  validation_results$required_fields <- validate_required_fields(data)
  validation_results$categories <- validate_categories(data)
  validation_results$percentages <- validate_percentages(data)
  validation_results$sample_sizes <- validate_sample_sizes(data)
  validation_results$dates <- validate_dates(data)
  
  # Overall validation status
  all_valid <- all(unlist(validation_results))
  
  cat("--- VALIDATION RESULTS ---\n")
  cat("Required fields:", ifelse(validation_results$required_fields, "✓ PASS", "✗ FAIL"), "\n")
  cat("Categories:", ifelse(validation_results$categories, "✓ PASS", "✗ FAIL"), "\n")
  cat("Percentages:", ifelse(validation_results$percentages, "✓ PASS", "✗ FAIL"), "\n")
  cat("Sample sizes:", ifelse(validation_results$sample_sizes, "✓ PASS", "✗ FAIL"), "\n")
  cat("Dates:", ifelse(validation_results$dates, "✓ PASS", "✗ FAIL"), "\n")
  cat("\nOverall validation:", ifelse(all_valid, "✓ PASS", "✗ FAIL"), "\n")
  
  return(list(valid = all_valid, results = validation_results))
}

# Data quality report
generate_quality_report <- function(data) {
  cat("\n=== DATA QUALITY REPORT ===\n")
  
  # Basic statistics
  cat("--- BASIC STATISTICS ---\n")
  cat("Total records:", nrow(data), "\n")
  cat("Unique questions:", length(unique(data$Question_Text)), "\n")
  cat("Countries:", length(unique(data$Country)), "\n")
  cat("Survey organizations:", length(unique(data$Survey_Organisation)), "\n")
  cat("Date range:", as.character(min(ymd(data$Fieldwork_Date), na.rm = TRUE)), 
      "to", as.character(max(ymd(data$Fieldwork_Date), na.rm = TRUE)), "\n")
  
  # Category distribution
  cat("\n--- CATEGORY DISTRIBUTION ---\n")
  category_counts <- table(data$Category)
  for (i in seq_along(category_counts)) {
    cat(names(category_counts)[i], ":", category_counts[i], "\n")
  }
  
  # Country distribution
  cat("\n--- TOP COUNTRIES ---\n")
  country_counts <- sort(table(data$Country), decreasing = TRUE)
  top_countries <- head(country_counts, 10)
  for (i in seq_along(top_countries)) {
    cat(names(top_countries)[i], ":", top_countries[i], "\n")
  }
  
  # Sample size statistics
  cat("\n--- SAMPLE SIZE STATISTICS ---\n")
  sample_stats <- data %>%
    filter(!is.na(N_Respondents)) %>%
    summarise(
      min_n = min(N_Respondents),
      max_n = max(N_Respondents),
      median_n = median(N_Respondents),
      mean_n = round(mean(N_Respondents))
    )
  
  cat("Min sample size:", sample_stats$min_n, "\n")
  cat("Max sample size:", sample_stats$max_n, "\n")
  cat("Median sample size:", sample_stats$median_n, "\n")
  cat("Mean sample size:", sample_stats$mean_n, "\n")
  
  # Agreement statistics
  cat("\n--- AGREEMENT STATISTICS ---\n")
  agreement_stats <- data %>%
    filter(!is.na(Agreement)) %>%
    summarise(
      min_agreement = min(Agreement),
      max_agreement = max(Agreement),
      median_agreement = median(Agreement),
      mean_agreement = round(mean(Agreement), 1)
    )
  
  cat("Min agreement:", agreement_stats$min_agreement, "%\n")
  cat("Max agreement:", agreement_stats$max_agreement, "%\n")
  cat("Median agreement:", agreement_stats$median_agreement, "%\n")
  cat("Mean agreement:", agreement_stats$mean_agreement, "%\n")
  
  # Missing data report
  cat("\n--- MISSING DATA REPORT ---\n")
  missing_data <- data %>%
    summarise(across(everything(), ~ sum(is.na(.) | . == ""))) %>%
    pivot_longer(everything(), names_to = "field", values_to = "missing_count") %>%
    filter(missing_count > 0) %>%
    arrange(desc(missing_count))
  
  if (nrow(missing_data) > 0) {
    for (i in 1:nrow(missing_data)) {
      cat(missing_data$field[i], ":", missing_data$missing_count[i], "missing\n")
    }
  } else {
    cat("No missing data found\n")
  }
}

# Clean data function
clean_polling_data <- function(data) {
  cat("=== CLEANING DATA ===\n")
  
  original_rows <- nrow(data)
  
  # Remove records with missing required fields
  data <- data %>%
    filter(!is.na(Question_Text) & Question_Text != "",
           !is.na(Agreement) & Agreement != "",
           !is.na(Country) & Country != "",
           !is.na(Survey_Organisation) & Survey_Organisation != "")
  
  # Convert percentages to numeric
  data <- data %>%
    mutate(
      Agreement = as.numeric(Agreement),
      Disagreement = as.numeric(Disagreement),
      Neutral = as.numeric(Neutral),
      N_Respondents = as.numeric(N_Respondents)
    )
  
  # Handle dates - check if already in Date format or needs parsing
  if (inherits(data$Fieldwork_Date, "Date")) {
    # Already correct Date format (from manual correction)
    data <- data %>%
      mutate(
        Fieldwork_Year = year(Fieldwork_Date),
        Fieldwork_Month = month(Fieldwork_Date)
      )
  } else {
    # Parse dates with improved handling (for AI-extracted dates)
    data <- data %>%
      mutate(
        # Clean and parse dates
        Fieldwork_Date_Clean = case_when(
          # Handle date ranges - take the start date
          str_detect(Fieldwork_Date, "to") ~ str_extract(Fieldwork_Date, "^[0-9]{4}-[0-9]{2}-[0-9]{2}"),
          # Handle seasonal dates
          str_detect(Fieldwork_Date, "Fall 2023") ~ "2023-10-01",
          str_detect(Fieldwork_Date, "Spring 2023") ~ "2023-04-01", 
          str_detect(Fieldwork_Date, "Summer 2023") ~ "2023-07-01",
          str_detect(Fieldwork_Date, "Winter 2023") ~ "2023-01-01",
          str_detect(Fieldwork_Date, "Fall 2024") ~ "2024-10-01",
          str_detect(Fieldwork_Date, "Spring 2024") ~ "2024-04-01",
          str_detect(Fieldwork_Date, "Summer 2024") ~ "2024-07-01", 
          str_detect(Fieldwork_Date, "Winter 2024") ~ "2024-01-01",
          # Handle already formatted dates
          str_detect(Fieldwork_Date, "^[0-9]{4}-[0-9]{2}-[0-9]{2}$") ~ Fieldwork_Date,
          TRUE ~ NA_character_
        ),
        Fieldwork_Date = ymd(Fieldwork_Date_Clean),
        Fieldwork_Year = year(Fieldwork_Date),
        Fieldwork_Month = month(Fieldwork_Date)
      ) %>%
      select(-Fieldwork_Date_Clean)
  }
  
  # Filter invalid categories
  data <- data %>%
    filter(Category %in% VALID_CATEGORIES)
  
  # Filter reasonable percentage ranges
  data <- data %>%
    filter(Agreement >= 0 & Agreement <= 100,
           Disagreement >= 0 & Disagreement <= 100,
           is.na(Neutral) | (Neutral >= 0 & Neutral <= 100))
  
  # Remove very small samples
  data <- data %>%
    filter(is.na(N_Respondents) | N_Respondents >= MIN_RESPONDENTS)
  
  cleaned_rows <- nrow(data)
  
  cat("Original records:", original_rows, "\n")
  cat("Cleaned records:", cleaned_rows, "\n")
  cat("Removed records:", original_rows - cleaned_rows, "\n")
  
  return(data)
}

# Main function for validation script
main <- function() {
  # Load data - prefer corrected version if available
  corrected_file <- file.path(EXTRACTED_DATA_DIR, "all_polling_data_corrected.rds")
  original_file <- file.path(EXTRACTED_DATA_DIR, "all_polling_data.rds")
  
  if (file.exists(corrected_file)) {
    data_file <- corrected_file
    cat("Using manually corrected dates from Google Sheet\n")
  } else if (file.exists(original_file)) {
    data_file <- original_file
    cat("Using AI-extracted dates\n")
  } else {
    stop("Data file not found. Please run extract_polling_data.R first.")
  }
  
  data <- readRDS(data_file)
  
  # Validate data
  validation_result <- validate_polling_data(data)
  
  # Generate quality report
  generate_quality_report(data)
  
  # Clean data
  cleaned_data <- clean_polling_data(data)
  
  # Save cleaned data
  clean_file <- file.path(EXTRACTED_DATA_DIR, "cleaned_polling_data.rds")
  saveRDS(cleaned_data, clean_file)
  
  # Save as CSV
  csv_file <- file.path(EXTRACTED_DATA_DIR, "cleaned_polling_data.csv")
  write_csv(cleaned_data, csv_file)
  
  cat("\n=== VALIDATION COMPLETE ===\n")
  cat("Cleaned data saved to:", clean_file, "\n")
  cat("CSV export saved to:", csv_file, "\n")
  
  return(cleaned_data)
}

# Run if not in interactive mode
if (!interactive()) {
  main()
}