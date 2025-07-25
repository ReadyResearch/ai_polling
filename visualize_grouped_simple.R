# Simple working visualization with hover text

library(tidyverse)
library(plotly)
library(htmlwidgets)

# Load data
full_data <- read_csv("extracted_data/polling_data_latest.csv", show_col_types = FALSE)
group_assignments <- read_csv("extracted_data/polling_data_grouped.csv", show_col_types = FALSE)

# Clean and join
grouped_data <- full_data %>%
  inner_join(
    group_assignments %>% 
      select(question_text, question_group) %>% 
      distinct(question_text, .keep_all = TRUE),
    by = "question_text"
  ) %>%
  mutate(
    fieldwork_date = as.Date(fieldwork_date),
    country_clean = case_when(
      str_detect(country, "United States|USA|US|U.S.") ~ "United States",
      str_detect(country, "United Kingdom|UK") ~ "United Kingdom",
      TRUE ~ country
    )
  ) %>%
  filter(
    !is.na(fieldwork_date),
    !is.na(agreement),
    !str_detect(question_group, "ungrouped")
  )

# Test with AI Extinction Risk Concern group
test_group <- "AI_Extinction_Risk_Concern"

group_data <- grouped_data %>%
  filter(question_group == test_group)

# Simple aggregation
plot_data <- group_data %>%
  group_by(country_clean, fieldwork_date) %>%
  summarise(
    agreement = mean(agreement, na.rm = TRUE),
    n_questions = n(),
    sample_size = sum(n_respondents, na.rm = TRUE),
    questions = paste(unique(substr(question_text, 1, 200)), collapse = " || "),
    .groups = "drop"
  )

# Create simple plot with hover text
p <- plot_ly()

for (country in unique(plot_data$country_clean)) {
  country_df <- plot_data %>% filter(country_clean == country)
  
  # Create hover text as a vector
  hover_vec <- paste0(
    "<b>", country, "</b><br>",
    "Date: ", country_df$fieldwork_date, "<br>",
    "Agreement: ", round(country_df$agreement, 1), "%<br>",
    "Sample: ", country_df$sample_size, "<br>",
    "Questions (", country_df$n_questions, "):<br>",
    country_df$questions
  )
  
  p <- p %>%
    add_trace(
      x = country_df$fieldwork_date,
      y = country_df$agreement,
      type = "scatter",
      mode = "markers",
      name = country,
      hoverinfo = "text",
      hovertext = hover_vec
    )
}

p <- p %>%
  layout(
    title = paste("AI Extinction Risk Concern"),
    xaxis = list(title = "Date"),
    yaxis = list(title = "Agreement (%)", range = c(0, 100))
  )

# Save
htmlwidgets::saveWidget(
  p,
  file = "test_simple_extinction.html",
  selfcontained = TRUE
)

print("Created test_simple_extinction.html")

# Check March 2025 specifically
march_2025 <- plot_data %>%
  filter(fieldwork_date == as.Date("2025-03-01"),
         country_clean == "United States")

if (nrow(march_2025) > 0) {
  cat("\nMarch 2025 US data:\n")
  cat("Agreement:", march_2025$agreement, "\n")
  cat("Sample size:", march_2025$sample_size, "\n")
  cat("Questions:", march_2025$questions, "\n")
}