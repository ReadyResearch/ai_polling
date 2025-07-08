#!/usr/bin/env Rscript

# Fetch manually verified dates from Google Sheets

library(tidyverse)

# Manual date mapping based on the Google Sheet data you provided
# PDF filename -> Month, Year, Accurate Fieldwork Date
manual_dates <- tribble(
  ~pdf_filename, ~month, ~year, ~fieldwork_start, ~country_region,
  "ada_lovelace_oct_2024", "Oct", 2024, "2024-10-25", "United Kingdom",
  "ai_impacts_oct_2023", "Oct", 2023, "2023-10-15", "Global (AI researchers)", 
  "aipi_jun_2024", "Jun", 2024, "2024-06-01", "United States",
  "aipi_nov_2024", "Nov", 2024, "2024-11-12", "United States",
  "aipi_aug_2024", "Aug", 2024, "2024-08-11", "United States",
  "deltapoll_oct_2023", "Oct", 2023, "2023-10-09", "9 countries",
  "gallup_apr_2024", "Apr", 2024, "2024-04-29", "United States",
  "harris_nov_2022", "Nov", 2022, "2022-11-03", "United States",
  "ipsos_nov_2021", "Nov", 2021, "2021-11-19", "Global",
  "ipsos_sep_2023", "Sep", 2023, "2023-09-14", "United Kingdom",
  "ipsos_oct_2023", "Oct", 2023, "2023-10-19", "17 countries",
  "ipsos_may_2023_global", "May", 2023, "2023-05-26", "31 countries", 
  "ipsos_april_2024", "April", 2024, "2024-04-19", "32 countries",
  "ipsos_mar_2024", "Mar", 2024, "2024-03-01", "United Kingdom",
  "ipsos_may_2023_us", "May", 2023, "2023-05-09", "United States",
  "kantar_nov_2022", "Nov", 2022, "2022-11-01", "United Kingdom",
  "monmouth_jan_2023", "Jan", 2023, "2023-01-26", "United States",
  "morning_consult_dec_2023", "Dec", 2023, "2023-12-01", "10-Country International",
  "3m_sep_2021", "Sep", 2021, "2021-09-01", "",
  "pew_aug_2024", "Aug", 2024, "2024-08-12", "United States",
  "rand_oct_2022", "Oct", 2022, "2022-10-17", "United States",
  "rethink_priorities_apr_2023", "Apr", 2023, "2023-04-14", "United States",
  "rethink_priorities_jul_2024", "Jul", 2024, "2024-07-31", "United Kingdom",
  "roy_morgan_aug_2023", "Aug", 2023, "2023-08-09", "Australia",
  "sara_jan_2024", "Jan", 2024, "2024-01-01", "Australia",
  "sentience_institute_nov_2021", "Nov", 2021, "2021-11-01", "United States",
  "sentience_institute_may_2023", "May", 2023, "2023-04-01", "United States",
  "umelb_nov_2024", "Nov", 2024, "2024-11-01", "Global",
  "unicri_nov_2022", "Nov", 2022, "2022-11-01", "Global",
  "university_of_toronto_oct_2023", "Oct", 2023, "2023-10-01", "21 countries",
  "vesely_kim_sep_2023", "Sep", 2023, "2023-09-01", "Germany, Spain",
  "yougov_apr_2023", "Apr", 2023, "2023-04-07", "United States",
  "yougov_aug_2023", "Aug", 2023, "2023-08-21", "United States", 
  "yougov_jul_2023", "Jul", 2023, "2023-07-18", "United States",
  "yougov_oct_2023", "Oct", 2023, "2023-10-18", "United Kingdom",
  "yougov_sep_2023", "Sep", 2023, "2023-09-02", "United States",
  "yougov_jan_2025", "Jan", 2025, "2024-01-16", "United Kingdom", # Note: Sheet shows Jan 2025 but date is 2024
  "yougov_mar_2025", "Mar", 2025, "2025-03-05", "United States",
  "yougov_may_2023", "May", 2023, "2023-05-31", "United Kingdom"
)

# Convert to date format and clean up
manual_dates <- manual_dates %>%
  mutate(
    fieldwork_date = as.Date(fieldwork_start),
    # Create mapping key from source file names
    source_file_key = case_when(
      pdf_filename == "ada_lovelace_oct_2024" ~ "ada_lovelace_2024.md",
      pdf_filename == "ai_impacts_oct_2023" ~ "ai_impacts_oct_2023.md", 
      pdf_filename == "gallup_apr_2024" ~ "gallup_apr_2024.md",
      pdf_filename == "harris_nov_2022" ~ "harris_nov_2022.md",
      TRUE ~ paste0(pdf_filename, ".md")
    )
  )

cat("Manual date mapping created with", nrow(manual_dates), "entries\n")

# Load current extracted data
if (file.exists("extracted_data/all_polling_data.rds")) {
  current_data <- readRDS("extracted_data/all_polling_data.rds")
  
  cat("\nCurrent data files:\n")
  print(unique(current_data$source_file))
  
  # Map the manual dates to our current files
  matched_dates <- manual_dates %>%
    filter(source_file_key %in% unique(current_data$source_file)) %>%
    select(source_file_key, fieldwork_date, country_region, month, year)
  
  cat("\nMatched dates for current files:\n")
  print(matched_dates)
  
  # Update the data with correct dates
  updated_data <- current_data %>%
    select(-Fieldwork_Date) %>%  # Remove AI-extracted dates
    left_join(matched_dates, by = c("source_file" = "source_file_key")) %>%
    rename(Fieldwork_Date = fieldwork_date) %>%
    mutate(
      Fieldwork_Year = year(Fieldwork_Date),
      Fieldwork_Month = month(Fieldwork_Date)
    )
  
  cat("\nUpdated data summary:\n")
  cat("Records with dates:", sum(!is.na(updated_data$Fieldwork_Date)), "out of", nrow(updated_data), "\n")
  cat("Date range:", as.character(min(updated_data$Fieldwork_Date, na.rm = TRUE)), 
      "to", as.character(max(updated_data$Fieldwork_Date, na.rm = TRUE)), "\n")
  
  # Save updated data
  saveRDS(updated_data, "extracted_data/all_polling_data_corrected.rds")
  write_csv(updated_data, "extracted_data/all_polling_data_corrected.csv")
  
  cat("\nCorrected data saved to:\n")
  cat("- extracted_data/all_polling_data_corrected.rds\n") 
  cat("- extracted_data/all_polling_data_corrected.csv\n")
  
} else {
  cat("No extracted data found. Please run data extraction first.\n")
}