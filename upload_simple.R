# Simple upload to Google Sheets - Manual approach
# Creates CSV files ready for manual upload

library(tidyverse)

cat("📤 Preparing stakeholder questions for Google Sheets upload...\n")

# Load the curated questions
stakeholder_questions <- read_csv("extracted_data/stakeholder_curated_questions.csv", show_col_types = FALSE)

# Create clean version for Google Sheets
clean_data <- stakeholder_questions %>%
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
  mutate(
    Date = as.character(Date),
    `Agreement %` = ifelse(is.na(`Agreement %`), "", as.character(`Agreement %`)),
    `Neutral %` = ifelse(is.na(`Neutral %`), "", as.character(`Neutral %`)),
    `Disagreement %` = ifelse(is.na(`Disagreement %`), "", as.character(`Disagreement %`)),
    # Clean text for Google Sheets
    Question = str_replace_all(Question, '"', '""'), # Escape quotes
    Question = str_trunc(Question, 500),
    Notes = str_replace_all(Notes, '"', '""'),
    Notes = str_trunc(Notes, 300),
    Justification = str_replace_all(Justification, '"', '""'),
    `Strategic Context` = str_replace_all(`Strategic Context`, '"', '""')
  )

# Save clean version
write_csv(clean_data, "extracted_data/stakeholder_questions_for_sheets.csv")

# Create summary data
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
    "Date Range"
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
    paste(min(stakeholder_questions$fieldwork_date, na.rm = TRUE), "to", max(stakeholder_questions$fieldwork_date, na.rm = TRUE))
  )
)

write_csv(summary_data, "extracted_data/stakeholder_summary_for_sheets.csv")

# Create instructions
instructions_data <- tibble(
  Section = c(
    "PURPOSE",
    "SELECTION CRITERIA - Policy advocacy",
    "SELECTION CRITERIA - Newsworthy content", 
    "SELECTION CRITERIA - Australian relevance",
    "SELECTION CRITERIA - Reputable sources",
    "SELECTION CRITERIA - Representative sampling",
    "SCORING - Strategic Value",
    "SCORING - Country Relevance", 
    "SCORING - Recency Score",
    "SCORING - Sample Quality",
    "SOURCES - SARA2024",
    "SOURCES - High Reputable",
    "SOURCES - Excluded",
    "USAGE - Ranking",
    "USAGE - Strategic Context",
    "USAGE - Data span"
  ),
  Description = c(
    "Top 100 AI polling questions for stakeholder sharing and policy advocacy",
    "Questions about AI regulation and governance", 
    "AI risks, job displacement, public concerns",
    "All SARA2024 questions included for baseline tracking",
    "Excluded ControlAI-funded polls, prioritized academic/government sources",
    "One question per semantic group to avoid redundancy",
    "3-10 points based on question type and policy relevance",
    "5-10 points: Australia=10, US=9, UK=8, etc.",
    "2-5 points: 2024=5, 2023=4, 2022=3, etc.",
    "1-5 points based on sample size",
    "University of Queensland (Australian baseline)",
    "Ada Lovelace Institute, UK Government, RAND, Pew, Ipsos",
    "YouGov polls funded by ControlAI due to perceived bias",
    "Questions ranked 1-100 by total score",
    "Use Strategic Context column to understand advocacy value",
    "Data spans 2022-2024 with focus on recent surveys"
  )
)

write_csv(instructions_data, "extracted_data/stakeholder_instructions_for_sheets.csv")

cat("\n✅ Files prepared for Google Sheets upload:\n")
cat("   📊 stakeholder_questions_for_sheets.csv - Main data (100 questions)\n")
cat("   📈 stakeholder_summary_for_sheets.csv - Summary statistics\n") 
cat("   📋 stakeholder_instructions_for_sheets.csv - Instructions and methodology\n")

cat("\n📋 MANUAL UPLOAD INSTRUCTIONS:\n")
cat("1. Open Google Sheets: https://docs.google.com/spreadsheets/d/1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE\n")
cat("2. Create new sheet tab: 'Stakeholder_Curated_Questions'\n")
cat("3. Import stakeholder_questions_for_sheets.csv\n")
cat("4. Create sheet tab: 'Stakeholder_Summary' and import summary CSV\n")
cat("5. Create sheet tab: 'Stakeholder_Instructions' and import instructions CSV\n")

# Show top 10 for preview
cat("\n🏆 TOP 10 QUESTIONS PREVIEW:\n")
top_10 <- clean_data %>% slice_head(n = 10)
for(i in 1:10) {
  cat(sprintf("%d. %s (%s, %s%%)\n", 
              top_10$Rank[i], 
              str_trunc(top_10$Question[i], 80),
              top_10$Country[i],
              top_10$`Agreement %`[i]))
}

cat("\n🎯 Files ready for manual upload to Google Sheets!\n")