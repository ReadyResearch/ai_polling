# Create Curated Stakeholder Question List
# Purpose: Select top 100 questions for stakeholder sharing based on strategic criteria

library(tidyverse)
library(readr)
library(openxlsx)

cat("🎯 Creating curated stakeholder question list...\n")

# Load data
polling_data <- read_csv("extracted_data/polling_data_latest.csv", show_col_types = FALSE)
grouped_data <- read_csv("extracted_data/polling_data_grouped.csv", show_col_types = FALSE)

# Clean and merge data
stakeholder_data <- polling_data %>%
  left_join(grouped_data %>% select(question_text, question_group, group_size), 
            by = "question_text") %>%
  mutate(
    # Clean organization names
    survey_org_clean = case_when(
      str_detect(survey_organisation, "University of Queensland") ~ "SARA2024 (University of Queensland)",
      str_detect(survey_organisation, "Ada Lovelace") ~ "Ada Lovelace Institute",
      str_detect(survey_organisation, "Deltapoll.*UK Gov") ~ "UK Government (Deltapoll)",
      str_detect(survey_organisation, "RAND") ~ "RAND Corporation",
      str_detect(survey_organisation, "Pew") ~ "Pew Research Center",
      str_detect(survey_organisation, "Ipsos") ~ "Ipsos",
      str_detect(survey_organisation, "YouGov.*ControlAI") ~ "YouGov (ControlAI-funded)", # Flag for exclusion
      str_detect(survey_organisation, "YouGov") ~ "YouGov",
      str_detect(survey_organisation, "AI Policy Institute|AIPI") ~ "AI Policy Institute",
      TRUE ~ survey_organisation
    ),
    
    # Determine source quality/reputation
    source_quality = case_when(
      str_detect(survey_org_clean, "SARA2024") ~ "high_priority", # Australian data
      str_detect(survey_org_clean, "Ada Lovelace|UK Government|RAND|Pew|Ipsos") ~ "high_reputable",
      str_detect(survey_org_clean, "AI Policy Institute") ~ "medium_reputable",
      str_detect(survey_org_clean, "YouGov.*ControlAI") ~ "exclude", # Exclude ControlAI-funded
      str_detect(survey_org_clean, "YouGov") ~ "medium_reputable",
      TRUE ~ "low_priority"
    ),
    
    # Determine question type for strategic value
    question_type = case_when(
      str_detect(tolower(question_text), "regulat|govern|policy|law") ~ "regulation_policy",
      str_detect(tolower(question_text), "risk|harm|danger|extinct|catastroph") ~ "risk_concern",
      str_detect(tolower(question_text), "job|work|employ|replac") ~ "job_displacement",
      str_detect(tolower(question_text), "trust|confiden|safe") ~ "trust_safety",
      str_detect(tolower(question_text), "benefit|good|harm|positive|negative") ~ "benefit_harm",
      str_detect(tolower(question_text), "familiar|understand|know|aware") ~ "awareness_knowledge",
      str_detect(tolower(question_text), "use|experience|interact") ~ "usage_experience",
      str_detect(tolower(question_text), "support|oppose|agree|disagree") ~ "support_opposition",
      TRUE ~ "other"
    ),
    
    # Strategic value scoring
    strategic_value = case_when(
      # High value: Regulation/policy questions (good for advocacy)
      question_type == "regulation_policy" ~ 10,
      # High value: Risk/harm questions (newsworthy, policy relevant)
      question_type == "risk_concern" ~ 9,
      # Medium-high: Trust/safety (policy relevant)
      question_type == "trust_safety" ~ 8,
      # Medium-high: Job displacement (newsworthy)
      question_type == "job_displacement" ~ 8,
      # Medium: Benefit/harm assessments (tracking attitudes)
      question_type == "benefit_harm" ~ 7,
      # Medium: Support/opposition (pulse tracking)
      question_type == "support_opposition" ~ 7,
      # Lower: Awareness/knowledge (less strategic)
      question_type == "awareness_knowledge" ~ 5,
      # Lower: Usage/experience (less strategic)
      question_type == "usage_experience" ~ 4,
      # Other
      TRUE ~ 3
    ),
    
    # Country relevance (prioritize Australia, major democracies)
    country_relevance = case_when(
      str_detect(country, "Australia") ~ 10,
      str_detect(country, "United States|USA|US") ~ 9,
      str_detect(country, "United Kingdom|UK|Britain") ~ 8,
      str_detect(country, "Canada|Germany|France|Netherlands|Sweden|Norway") ~ 7,
      str_detect(country, "Global|International|Worldwide") ~ 6,
      TRUE ~ 5
    ),
    
    # Recency bonus (more recent = more relevant)
    recency_score = case_when(
      fieldwork_date >= as.Date("2024-01-01") ~ 5,
      fieldwork_date >= as.Date("2023-01-01") ~ 4,
      fieldwork_date >= as.Date("2022-01-01") ~ 3,
      TRUE ~ 2
    ),
    
    # Sample size quality
    sample_quality = case_when(
      n_respondents >= 2000 ~ 5,
      n_respondents >= 1000 ~ 4,
      n_respondents >= 500 ~ 3,
      n_respondents >= 200 ~ 2,
      TRUE ~ 1
    ),
    
    # Calculate total score
    total_score = case_when(
      source_quality == "exclude" ~ 0, # Exclude ControlAI-funded
      source_quality == "high_priority" ~ strategic_value + country_relevance + recency_score + sample_quality + 15, # SARA2024 bonus
      source_quality == "high_reputable" ~ strategic_value + country_relevance + recency_score + sample_quality + 10,
      source_quality == "medium_reputable" ~ strategic_value + country_relevance + recency_score + sample_quality + 5,
      TRUE ~ strategic_value + country_relevance + recency_score + sample_quality
    )
  ) %>%
  filter(source_quality != "exclude") %>% # Remove ControlAI-funded polls
  arrange(desc(total_score))

# Select representative questions from each semantic group
group_representatives <- stakeholder_data %>%
  filter(!is.na(question_group), !str_detect(question_group, "^ungrouped_")) %>%
  group_by(question_group) %>%
  slice_max(total_score, n = 1) %>%
  ungroup() %>%
  mutate(selection_reason = "Representative of semantic group")

# Get all SARA2024 questions
sara_questions <- stakeholder_data %>%
  filter(str_detect(survey_org_clean, "SARA2024")) %>%
  mutate(selection_reason = "SARA2024 - Australian baseline")

# Get high-scoring questions from reputable sources
high_scoring_questions <- stakeholder_data %>%
  filter(
    source_quality %in% c("high_reputable", "medium_reputable"),
    total_score >= 25, # High threshold
    !question_text %in% c(group_representatives$question_text, sara_questions$question_text)
  ) %>%
  mutate(selection_reason = "High strategic value from reputable source")

# Combine all selected questions
selected_questions <- bind_rows(
  group_representatives,
  sara_questions,
  high_scoring_questions
) %>%
  distinct(question_text, .keep_all = TRUE) %>%
  arrange(desc(total_score)) %>%
  slice_head(n = 100) %>%
  mutate(
    rank = row_number(),
    # Create justification
    justification = case_when(
      str_detect(selection_reason, "SARA2024") ~ "Australian baseline data - critical for tracking domestic attitudes",
      str_detect(selection_reason, "Representative") ~ paste0("Best representative of '", str_replace_all(question_group, "_", " "), "' theme"),
      strategic_value >= 9 ~ "High policy advocacy value - regulation/risk questions",
      strategic_value >= 8 ~ "Medium-high strategic value - trust/safety/jobs",
      strategic_value >= 7 ~ "Medium strategic value - attitudes/support tracking",
      TRUE ~ "Selected for completeness"
    ),
    
    # Add strategic context
    strategic_context = case_when(
      question_type == "regulation_policy" ~ "Policy advocacy: Demonstrates public support for AI regulation",
      question_type == "risk_concern" ~ "Risk communication: Shows public concern about AI risks",
      question_type == "trust_safety" ~ "Trust building: Reveals public trust gaps in AI safety",
      question_type == "job_displacement" ~ "Economic impact: Tracks job displacement concerns",
      question_type == "benefit_harm" ~ "Balanced perspective: Overall AI sentiment tracking",
      question_type == "support_opposition" ~ "Political feasibility: Public support for specific measures",
      TRUE ~ "Contextual: Provides background understanding"
    )
  ) %>%
  select(
    rank,
    question_text,
    category,
    survey_org_clean,
    country,
    fieldwork_date,
    agreement,
    neutral,
    disagreement,
    n_respondents,
    response_scale,
    question_type,
    strategic_value,
    country_relevance,
    recency_score,
    sample_quality,
    total_score,
    selection_reason,
    justification,
    strategic_context,
    notes
  )

# Create summary stats
summary_stats <- selected_questions %>%
  summarise(
    total_questions = n(),
    sara_questions = sum(str_detect(survey_org_clean, "SARA2024")),
    high_reputable = sum(str_detect(survey_org_clean, "Ada Lovelace|UK Government|RAND|Pew|Ipsos")),
    australia_questions = sum(str_detect(country, "Australia")),
    us_questions = sum(str_detect(country, "United States|USA|US")),
    uk_questions = sum(str_detect(country, "United Kingdom|UK|Britain")),
    regulation_questions = sum(question_type == "regulation_policy"),
    risk_questions = sum(question_type == "risk_concern"),
    trust_questions = sum(question_type == "trust_safety"),
    job_questions = sum(question_type == "job_displacement"),
    avg_agreement = round(mean(agreement, na.rm = TRUE), 1),
    median_sample_size = median(n_respondents, na.rm = TRUE),
    date_range = paste(min(fieldwork_date, na.rm = TRUE), "to", max(fieldwork_date, na.rm = TRUE))
  )

# Print summary
cat("\n📊 STAKEHOLDER QUESTION LIST SUMMARY\n")
cat("=====================================\n")
cat(sprintf("Total questions selected: %d\n", summary_stats$total_questions))
cat(sprintf("SARA2024 questions: %d\n", summary_stats$sara_questions))
cat(sprintf("High reputable sources: %d\n", summary_stats$high_reputable))
cat(sprintf("Australia questions: %d\n", summary_stats$australia_questions))
cat(sprintf("US questions: %d\n", summary_stats$us_questions))
cat(sprintf("UK questions: %d\n", summary_stats$uk_questions))
cat(sprintf("Regulation/policy questions: %d\n", summary_stats$regulation_questions))
cat(sprintf("Risk/concern questions: %d\n", summary_stats$risk_questions))
cat(sprintf("Trust/safety questions: %d\n", summary_stats$trust_questions))
cat(sprintf("Job displacement questions: %d\n", summary_stats$job_questions))
cat(sprintf("Average agreement: %s%%\n", summary_stats$avg_agreement))
cat(sprintf("Median sample size: %d\n", summary_stats$median_sample_size))
cat(sprintf("Date range: %s\n", summary_stats$date_range))

# Save to CSV
write_csv(selected_questions, "extracted_data/stakeholder_curated_questions.csv")
cat("\n✅ Saved to: extracted_data/stakeholder_curated_questions.csv\n")

# Create Excel file with formatted tabs
wb <- createWorkbook()

# Main stakeholder list
addWorksheet(wb, "Stakeholder Questions")
writeData(wb, "Stakeholder Questions", selected_questions)

# Add conditional formatting for scores
conditionalFormatting(wb, "Stakeholder Questions", 
                     cols = which(names(selected_questions) == "total_score"),
                     rows = 2:(nrow(selected_questions) + 1),
                     style = c("#FF6B6B", "#4ECDC4"),
                     rule = c(min(selected_questions$total_score), max(selected_questions$total_score)),
                     type = "colourScale")

# Summary tab
addWorksheet(wb, "Summary")
summary_df <- data.frame(
  Metric = c("Total Questions", "SARA2024 Questions", "High Reputable Sources", 
             "Australia Questions", "US Questions", "UK Questions",
             "Regulation Questions", "Risk Questions", "Trust Questions", "Job Questions",
             "Average Agreement", "Median Sample Size", "Date Range"),
  Value = c(summary_stats$total_questions, summary_stats$sara_questions, summary_stats$high_reputable,
            summary_stats$australia_questions, summary_stats$us_questions, summary_stats$uk_questions,
            summary_stats$regulation_questions, summary_stats$risk_questions, summary_stats$trust_questions,
            summary_stats$job_questions, paste0(summary_stats$avg_agreement, "%"),
            summary_stats$median_sample_size, summary_stats$date_range)
)
writeData(wb, "Summary", summary_df)

# Top 20 by category
addWorksheet(wb, "Top by Category")
top_by_category <- selected_questions %>%
  group_by(question_type) %>%
  slice_head(n = 5) %>%
  ungroup() %>%
  arrange(question_type, desc(total_score)) %>%
  select(question_type, rank, question_text, survey_org_clean, country, agreement, total_score)
writeData(wb, "Top by Category", top_by_category)

# Save Excel file
saveWorkbook(wb, "extracted_data/stakeholder_curated_questions.xlsx", overwrite = TRUE)
cat("✅ Saved to: extracted_data/stakeholder_curated_questions.xlsx\n")

# Show top 10 questions
cat("\n🏆 TOP 10 STAKEHOLDER QUESTIONS:\n")
cat("================================\n")
top_10 <- selected_questions %>%
  slice_head(n = 10) %>%
  select(rank, question_text, survey_org_clean, country, agreement, total_score, justification)

for (i in 1:nrow(top_10)) {
  cat(sprintf("%d. %s\n", top_10$rank[i], str_trunc(top_10$question_text[i], 80)))
  cat(sprintf("   Source: %s (%s) | Agreement: %s%% | Score: %d\n", 
              top_10$survey_org_clean[i], top_10$country[i], top_10$agreement[i], top_10$total_score[i]))
  cat(sprintf("   Rationale: %s\n\n", top_10$justification[i]))
}

cat("🎯 Stakeholder list creation complete!\n")