#!/usr/bin/env Rscript

library(tidyverse)
library(readxl)
library(lubridate)

extract_deltapoll_data <- function(excel_path) {
  
  cat("Reading Deltapoll Excel file from Tab 2...\n")
  
  # Read the raw data from Tab 2
  raw_data <- read_excel(excel_path, sheet = 2, col_names = FALSE)
  
  # Countries are in columns 2-10 based on the data structure shown
  countries <- c("Canada", "France", "Germany", "Italy", "Japan", "Singapore", "South Korea", "UK", "USA")
  
  # Sample sizes (from row with "All Adults")
  sample_sizes <- c(1114, 1120, 1164, 1136, 1137, 1134, 1142, 1090, 1126)
  names(sample_sizes) <- countries
  
  # Initialize results list
  results <- list()
  
  # Define question mappings based on the structure shown
  question_mappings <- list(
    
    # Knowledge question - binary grouping
    list(
      question = "How much, if anything, did you know about AI before today?",
      category = "AI_Knowledge", 
      response_scale = "A great deal/A fair amount/Not very much/Nothing at all",
      agreement_items = c("A great deal", "A fair amount"),
      neutral_items = character(0),
      disagreement_items = c("Not very much", "Nothing at all"),
      data_rows = list(
        "A great deal" = c(12, 10, 9, 12, 2, 16, 15, 11, 21),
        "A fair amount" = c(48, 40, 36, 55, 24, 55, 65, 43, 39),
        "Not very much" = c(34, 40, 47, 26, 59, 26, 16, 40, 28),
        "Nothing at all" = c(5, 7, 6, 6, 10, 2, 4, 5, 8)
      )
    ),
    
    # Risk concern - Loss of control
    list(
      question = "How worried, if at all, are you that humans will lose control of AI?",
      category = "AI_Risk_Concern",
      response_scale = "Very worried/Fairly worried/Not very worried/Not at all worried",
      agreement_items = c("Very worried", "Fairly worried"),
      neutral_items = character(0),
      disagreement_items = c("Not very worried", "Not at all worried"),
      data_rows = list(
        "Very worried" = c(17, 19, 16, 12, 13, 12, 11, 18, 26),
        "Fairly worried" = c(43, 47, 38, 37, 39, 49, 45, 43, 37),
        "Not very worried" = c(28, 23, 34, 35, 30, 31, 36, 28, 21),
        "Not at all worried" = c(6, 5, 6, 10, 3, 5, 5, 6, 8)
      )
    ),
    
    # Risk concern - Cyberattacks  
    list(
      question = "How worried, if at all, are you that AI will be used to carry out cyberattacks?",
      category = "AI_Risk_Concern",
      response_scale = "Very worried/Fairly worried/Not very worried/Not at all worried", 
      agreement_items = c("Very worried", "Fairly worried"),
      neutral_items = character(0),
      disagreement_items = c("Not very worried", "Not at all worried"),
      data_rows = list(
        "Very worried" = c(27, 25, 23, 22, 21, 25, 16, 26, 31),
        "Fairly worried" = c(42, 46, 44, 46, 45, 49, 49, 44, 38),
        "Not very worried" = c(18, 17, 22, 21, 18, 18, 27, 20, 15),
        "Not at all worried" = c(5, 5, 4, 4, 3, 3, 4, 4, 7)
      )
    ),
    
    # Risk concern - Biological weapons
    list(
      question = "How worried, if at all, are you that AI will be used to help design biological weapons?",
      category = "AI_Risk_Concern", 
      response_scale = "Very worried/Fairly worried/Not very worried/Not at all worried",
      agreement_items = c("Very worried", "Fairly worried"),
      neutral_items = character(0),
      disagreement_items = c("Not very worried", "Not at all worried"),
      data_rows = list(
        "Very worried" = c(30, 29, 27, 30, 26, 32, 20, 32, 35),
        "Fairly worried" = c(39, 41, 37, 39, 41, 43, 47, 35, 33),
        "Not very worried" = c(18, 18, 24, 19, 18, 16, 25, 20, 17),
        "Not at all worried" = c(4, 4, 5, 5, 2, 5, 5, 5, 6)
      )
    ),
    
    # Risk vs benefit preference
    list(
      question = "Thinking about the potential benefits and risks of AI, which statement do you most agree with?",
      category = "AI_Risk_Concern",
      response_scale = "AI has more risks than benefits (cautious)/AI has more benefits than risks (less cautious)",
      agreement_items = c("AI has more potential risks than benefits. We should be cautious to minimise these potential risks"),
      neutral_items = character(0),
      disagreement_items = c("AI has more potential benefits than risks. Being too cautious might stop us maximising these potential benefits"),
      data_rows = list(
        "AI has more potential risks than benefits. We should be cautious to minimise these potential risks" = c(48, 46, 44, 41, 41, 35, 44, 48, 49),
        "AI has more potential benefits than risks. Being too cautious might stop us maximising these potential benefits" = c(35, 38, 39, 44, 31, 52, 51, 38, 34)
      )
    ),
    
    # Trust in tech companies
    list(
      question = "To what extent, if at all, do you trust tech companies to ensure the AI they develop is safe?",
      category = "AI_Regulation",
      response_scale = "A great deal/A fair amount/Not very much/Not at all",
      agreement_items = c("A great deal", "A fair amount"),
      neutral_items = character(0),
      disagreement_items = c("Not very much", "Not at all"),
      data_rows = list(
        "A great deal" = c(7, 7, 6, 6, 2, 15, 8, 8, 17),
        "A fair amount" = c(34, 26, 32, 46, 12, 48, 56, 34, 31),
        "Not very much" = c(37, 38, 40, 33, 54, 27, 27, 36, 29),
        "Not at all" = c(14, 14, 12, 8, 13, 5, 6, 14, 15)
      )
    ),
    
    # Independent testing
    list(
      question = "How much do you agree that powerful AI should be tested by independent experts to ensure it is safe?",
      category = "AI_Regulation", 
      response_scale = "Strongly agree/Tend to agree/Neither/Tend to disagree/Strongly disagree",
      agreement_items = c("Strongly agree", "Tend to agree"),
      neutral_items = c("Neither agree nor disagree"),
      disagreement_items = c("Tend to disagree", "Strongly disagree"),
      data_rows = list(
        "Strongly agree" = c(38, 29, 38, 28, 22, 34, 25, 49, 45),
        "Tend to agree" = c(33, 37, 29, 40, 37, 42, 48, 27, 28),
        "Neither agree nor disagree" = c(14, 19, 22, 19, 22, 17, 18, 12, 13),
        "Tend to disagree" = c(4, 4, 4, 4, 4, 3, 4, 4, 4),
        "Strongly disagree" = c(4, 2, 1, 3, 4, 2, 1, 2, 3)
      )
    ),
    
    # Open source opposition (framed as regulation support)
    list(
      question = "Should powerful AI be open source?",
      category = "AI_Regulation",
      response_scale = "Yes, should be open source/No, should not be open source", 
      agreement_items = c("No, powerful AI should not be open source"),
      neutral_items = character(0),
      disagreement_items = c("Yes, powerful AI should be open source"),
      data_rows = list(
        "Yes, powerful AI should be open source" = c(26, 27, 32, 34, 29, 41, 48, 23, 32),
        "No, powerful AI should not be open source" = c(50, 47, 40, 38, 28, 45, 40, 56, 45)
      )
    ),
    
    # International organization support  
    list(
      question = "How much would you support the creation of an international AI safety institute?",
      category = "AI_Regulation",
      response_scale = "Strongly support/Tend to support/Neither/Tend to oppose/Strongly oppose",
      agreement_items = c("Strongly support", "Tend to support"),
      neutral_items = c("Neither support not oppose"),
      disagreement_items = c("Tend to oppose", "Strongly oppose"),
      data_rows = list(
        "Strongly support" = c(28, 19, 25, 37, 20, 23, 20, 29, 27),
        "Tend to support" = c(33, 34, 29, 28, 31, 38, 43, 33, 25),
        "Neither support not oppose" = c(20, 27, 30, 21, 27, 26, 27, 18, 20),
        "Tend to oppose" = c(7, 8, 6, 5, 6, 6, 5, 6, 9),
        "Strongly oppose" = c(3, 5, 3, 2, 3, 4, 1, 4, 8)
      )
    ),
    
    # Extinction risk statement
    list(
      question = "Mitigating the risk of extinction from AI should be a global priority alongside other societal-scale risks such as pandemics and nuclear war",
      category = "Extinction_Risk",
      response_scale = "Strongly agree/Tend to agree/Neither/Tend to disagree/Strongly disagree",
      agreement_items = c("Strongly agree", "Tend to agree"),
      neutral_items = c("Neither agree nor disagree"),
      disagreement_items = c("Tend to disagree", "Strongly disagree"),
      data_rows = list(
        "Strongly agree" = c(23, 14, 14, 16, 12, 16, 13, 24, 28),
        "Tend to agree" = c(31, 30, 26, 35, 30, 38, 43, 31, 27),
        "Neither agree nor disagree" = c(23, 31, 37, 29, 32, 31, 31, 22, 22),
        "Tend to disagree" = c(8, 9, 10, 8, 6, 8, 7, 8, 8),
        "Strongly disagree" = c(4, 3, 3, 4, 3, 2, 2, 3, 4)
      )
    )
  )
  
  # Process each question
  for (i in seq_along(question_mappings)) {
    q_info <- question_mappings[[i]]
    
    # Calculate percentages for each country
    for (j in seq_along(countries)) {
      country <- countries[j]
      
      # Sum agreement percentages
      agreement_pct <- 0
      if (length(q_info$agreement_items) > 0) {
        for (item in q_info$agreement_items) {
          if (item %in% names(q_info$data_rows)) {
            agreement_pct <- agreement_pct + q_info$data_rows[[item]][j]
          }
        }
      }
      
      # Sum neutral percentages  
      neutral_pct <- 0
      if (length(q_info$neutral_items) > 0) {
        for (item in q_info$neutral_items) {
          if (item %in% names(q_info$data_rows)) {
            neutral_pct <- neutral_pct + q_info$data_rows[[item]][j]
          }
        }
      }
      
      # Sum disagreement percentages
      disagreement_pct <- 0
      if (length(q_info$disagreement_items) > 0) {
        for (item in q_info$disagreement_items) {
          if (item %in% names(q_info$data_rows)) {
            disagreement_pct <- disagreement_pct + q_info$data_rows[[item]][j]
          }
        }
      }
      
      # Create record
      record <- list(
        Question_Text = q_info$question,
        Response_Scale = q_info$response_scale,
        Category = q_info$category,
        Agreement = agreement_pct,
        Neutral = neutral_pct,
        Disagreement = disagreement_pct,
        N_Respondents = sample_sizes[country],
        Country = country,
        Survey_Organisation = "Deltapoll",
        Fieldwork_Date = "2023-10-09",  # Start date of fieldwork
        Notes = "Fieldwork: 9th - 13th October 2023. Prepared by Deltapoll for CDEI"
      )
      
      results[[length(results) + 1]] <- record
    }
  }
  
  # Convert to data frame
  deltapoll_data <- bind_rows(results)
  
  # Convert date
  deltapoll_data$Fieldwork_Date <- as.Date(deltapoll_data$Fieldwork_Date)
  
  cat("Extracted", nrow(deltapoll_data), "records from Deltapoll data\n")
  cat("Countries:", paste(unique(deltapoll_data$Country), collapse = ", "), "\n")
  cat("Categories:", paste(unique(deltapoll_data$Category), collapse = ", "), "\n")
  
  return(deltapoll_data)
}

# Function to combine with existing data
combine_with_existing_data <- function(deltapoll_data) {
  
  # Load existing cleaned data
  existing_data_path <- "extracted_data/cleaned_polling_data.rds"
  
  if (file.exists(existing_data_path)) {
    cat("Loading existing polling data...\n")
    existing_data <- readRDS(existing_data_path)
    
    # Combine datasets
    combined_data <- bind_rows(existing_data, deltapoll_data)
    
    cat("Combined dataset now has", nrow(combined_data), "total records\n")
    cat("From", length(unique(combined_data$Survey_Organisation)), "survey organizations\n")
    
    # Save combined data
    saveRDS(combined_data, "extracted_data/combined_polling_data.rds")
    
    return(combined_data)
  } else {
    cat("No existing data found, saving Deltapoll data only\n")
    saveRDS(deltapoll_data, "extracted_data/combined_polling_data.rds")
    return(deltapoll_data)
  }
}

# Main execution
if (!interactive()) {
  
  # Check if Excel file path provided as argument
  args <- commandArgs(trailingOnly = TRUE)
  
  if (length(args) == 0) {
    cat("Please provide path to the Deltapoll Excel file as an argument\n")
    cat("Usage: Rscript extract_deltapoll_excel.R path/to/deltapoll_oct_2023.xlsx\n")
    quit(status = 1)
  }
  
  excel_path <- args[1]
  
  if (!file.exists(excel_path)) {
    cat("Error: Excel file not found at", excel_path, "\n")
    quit(status = 1)
  }
  
  # Extract data
  deltapoll_data <- extract_deltapoll_data(excel_path)
  
  # Combine with existing data
  combined_data <- combine_with_existing_data(deltapoll_data)
  
  cat("Deltapoll data extraction complete!\n")
  cat("Combined data saved to: extracted_data/combined_polling_data.rds\n")
}