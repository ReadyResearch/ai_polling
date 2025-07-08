# Upload Stakeholder Questions to Google Sheets
# Creates a new tab in the existing Google Sheet

library(tidyverse)
library(googlesheets4)
library(googledrive)

cat("📤 Uploading stakeholder questions to Google Sheets...\n")

# Authenticate with Google (will prompt for authentication if needed)
gs4_auth()

# Load the curated questions
stakeholder_questions <- read_csv("extracted_data/stakeholder_curated_questions.csv", show_col_types = FALSE)

# The sheet URL from CLAUDE.md
sheet_url <- "https://docs.google.com/spreadsheets/d/1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE"

cat("🔗 Connecting to Google Sheet...\n")

# Get the sheet ID
sheet_id <- gs4_get(sheet_url)

# Check existing sheet names
existing_sheets <- sheet_names(sheet_id)
cat("📋 Existing sheets:", paste(existing_sheets, collapse = ", "), "\n")

# Create a new sheet for stakeholder questions
new_sheet_name <- "Stakeholder_Curated_Questions"

# Remove sheet if it already exists
if (new_sheet_name %in% existing_sheets) {
  cat("🗑️ Removing existing sheet:", new_sheet_name, "\n")
  sheet_delete(sheet_id, new_sheet_name)
}

# Add new sheet
cat("➕ Creating new sheet:", new_sheet_name, "\n")
sheet_add(sheet_id, sheet = new_sheet_name)

# Select columns to upload (clean version for stakeholders)
upload_data <- stakeholder_questions %>%
  select(
    Rank = rank,
    Question = question_text,
    Category = category,
    Organization = survey_org_clean,
    Country = country,
    Date = fieldwork_date,
    `Agreement %` = agreement,
    `Neutral %` = neutral,
    `Disagreement %` = disagreement,
    `Sample Size` = n_respondents,
    `Response Scale` = response_scale,
    `Strategic Value` = strategic_value,
    `Total Score` = total_score,
    `Selection Reason` = selection_reason,
    Justification = justification,
    `Strategic Context` = strategic_context,
    Notes = notes
  ) %>%
  # Clean up data for presentation
  mutate(
    Date = as.character(Date),
    `Agreement %` = ifelse(is.na(`Agreement %`), "", as.character(`Agreement %`)),
    `Neutral %` = ifelse(is.na(`Neutral %`), "", as.character(`Neutral %`)),
    `Disagreement %` = ifelse(is.na(`Disagreement %`), "", as.character(`Disagreement %`)),
    Question = str_trunc(Question, 500), # Prevent cell overflow
    Notes = str_trunc(Notes, 300)
  )

cat("📊 Uploading", nrow(upload_data), "questions to Google Sheets...\n")

# Write data to the sheet
sheet_write(upload_data, ss = sheet_id, sheet = new_sheet_name)

# Create a summary sheet
summary_data <- tibble(
  Metric = c(
    "Total Questions Selected",
    "SARA2024 Australian Questions", 
    "High Reputable Sources",
    "Australia Questions",
    "US Questions", 
    "UK Questions",
    "Regulation/Policy Questions",
    "Risk/Concern Questions", 
    "Trust/Safety Questions",
    "Job Displacement Questions",
    "Average Agreement %",
    "Median Sample Size",
    "Date Range",
    "Selection Criteria",
    "",
    "Top Source Organizations",
    "",
    "Question Type Distribution",
    ""
  ),
  Value = c(
    nrow(stakeholder_questions),
    sum(str_detect(stakeholder_questions$survey_org_clean, "SARA2024")),
    sum(str_detect(stakeholder_questions$survey_org_clean, "Ada Lovelace|UK Government|RAND|Pew|Ipsos")),
    sum(str_detect(stakeholder_questions$country, "Australia")),
    sum(str_detect(stakeholder_questions$country, "United States|USA|US")),
    sum(str_detect(stakeholder_questions$country, "United Kingdom|UK|Britain")),
    sum(stakeholder_questions$question_type == "regulation_policy"),
    sum(stakeholder_questions$question_type == "risk_concern"),
    sum(stakeholder_questions$question_type == "trust_safety"),
    sum(stakeholder_questions$question_type == "job_displacement"),
    paste0(round(mean(stakeholder_questions$agreement, na.rm = TRUE), 1), "%"),
    format(median(stakeholder_questions$n_respondents, na.rm = TRUE), big.mark = ","),
    paste(min(stakeholder_questions$fieldwork_date, na.rm = TRUE), "to", max(stakeholder_questions$fieldwork_date, na.rm = TRUE)),
    "Policy advocacy, newsworthy content, Australian relevance, reputable sources",
    "",
    paste(table(stakeholder_questions$survey_org_clean)[1:5], collapse = ", "),
    "",
    paste(names(table(stakeholder_questions$question_type)), table(stakeholder_questions$question_type), sep = ": ", collapse = "; "),
    ""
  )
)

# Create summary sheet
summary_sheet_name <- "Stakeholder_Summary"

# Remove summary sheet if it already exists
if (summary_sheet_name %in% sheet_names(sheet_id)) {
  cat("🗑️ Removing existing summary sheet:", summary_sheet_name, "\n")
  sheet_delete(sheet_id, summary_sheet_name)
}

# Add summary sheet
cat("➕ Creating summary sheet:", summary_sheet_name, "\n")
sheet_add(sheet_id, sheet = summary_sheet_name)

# Write summary data
sheet_write(summary_data, ss = sheet_id, sheet = summary_sheet_name)

# Add a description/instructions sheet
instructions_data <- tibble(
  Section = c(
    "PURPOSE",
    "",
    "SELECTION CRITERIA",
    "",
    "",
    "",
    "",
    "",
    "SCORING SYSTEM",
    "",
    "",
    "",
    "",
    "",
    "DATA SOURCES",
    "",
    "",
    "",
    "",
    "USAGE NOTES",
    "",
    "",
    ""
  ),
  Description = c(
    "This curated list contains the top 100 AI polling questions selected for stakeholder sharing and policy advocacy.",
    "",
    "• Policy advocacy value: Questions about AI regulation and governance",
    "• Newsworthy content: AI risks, job displacement, public concerns", 
    "• Australian relevance: All SARA2024 questions included for baseline tracking",
    "• Reputable sources: Excluded ControlAI-funded polls, prioritized academic/government sources",
    "• Representative sampling: One question per semantic group to avoid redundancy",
    "• Pulse tracking: Key questions for monitoring attitude changes over time",
    "",
    "• Strategic Value (3-10): Based on question type and policy relevance",
    "• Country Relevance (5-10): Australia=10, US=9, UK=8, etc.",
    "• Recency Score (2-5): 2024=5, 2023=4, 2022=3, etc.", 
    "• Sample Quality (1-5): Based on sample size",
    "• Source Quality Bonus: SARA2024=+15, High reputable=+10, Medium=+5",
    "",
    "• SARA2024: University of Queensland (Australian baseline)",
    "• High Reputable: Ada Lovelace Institute, UK Government, RAND, Pew, Ipsos",
    "• Medium Reputable: AI Policy Institute, YouGov (non-ControlAI)",
    "• Excluded: YouGov polls funded by ControlAI due to perceived bias",
    "",
    "• Questions ranked 1-100 by total score",
    "• Use 'Strategic Context' column to understand advocacy value",
    "• 'Justification' explains why each question was selected",
    "• Data spans 2022-2024 with focus on recent surveys"
  )
)

instructions_sheet_name <- "Instructions"

# Remove instructions sheet if it already exists  
if (instructions_sheet_name %in% sheet_names(sheet_id)) {
  cat("🗑️ Removing existing instructions sheet:", instructions_sheet_name, "\n")
  sheet_delete(sheet_id, instructions_sheet_name)
}

# Add instructions sheet
cat("➕ Creating instructions sheet:", instructions_sheet_name, "\n")
sheet_add(sheet_id, sheet = instructions_sheet_name)

# Write instructions
sheet_write(instructions_data, ss = sheet_id, sheet = instructions_sheet_name)

cat("\n✅ Upload complete! Created 3 new sheets:\n")
cat("   📊", new_sheet_name, "- Main stakeholder questions (100 items)\n")
cat("   📈", summary_sheet_name, "- Summary statistics and overview\n") 
cat("   📋", instructions_sheet_name, "- Usage instructions and methodology\n")
cat("\n🔗 View at:", sheet_url, "\n")

cat("\n🎯 Stakeholder upload complete!\n")