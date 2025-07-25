# AI Polling Data Visualization - Refactored Version
# This version ensures question text is ALWAYS available in hover

# Load required libraries
if (!require("pacman")) install.packages("pacman")
pacman::p_load(
  tidyverse, plotly, lubridate, htmlwidgets, 
  scales, viridis, RColorBrewer, htmltools, jsonlite
)

# Create visualizations directory
if (!dir.exists("visualizations_grouped")) {
  dir.create("visualizations_grouped")
}

print("📊 Loading and processing polling data...")

# Load the full dataset
full_data <- read_csv("extracted_data/polling_data_latest.csv", 
                     show_col_types = FALSE)

# Load the grouped data
group_assignments <- read_csv("extracted_data/polling_data_grouped.csv", 
                             show_col_types = FALSE)

print(sprintf("✅ Loaded %d full records and %d group assignments", 
              nrow(full_data), nrow(group_assignments)))

# Clean and prepare data
print("🔧 Processing data with enhanced question tracking...")

# First, ensure unique group assignments
group_assignments_clean <- group_assignments %>%
  select(question_text, question_group, group_size) %>%
  distinct(question_text, .keep_all = TRUE)

# Join and process - KEEPING QUESTION TEXT AT EVERY STEP
grouped_data <- full_data %>%
  inner_join(
    group_assignments_clean,
    by = "question_text",
    relationship = "many-to-one"
  ) %>%
  # Clean data
  mutate(
    fieldwork_date = as.Date(fieldwork_date),
    year_month = floor_date(fieldwork_date, "month"),
    country_clean = case_when(
      str_detect(country, "United States|USA|US|U.S.") ~ "United States",
      str_detect(country, "United Kingdom|UK|Britain") ~ "United Kingdom", 
      str_detect(country, "Global|International|Worldwide") ~ "Global",
      TRUE ~ country
    ),
    agreement = as.numeric(agreement),
    neutral = as.numeric(neutral),
    disagreement = as.numeric(disagreement),
    # Escape % signs in question text RIGHT AWAY
    question_text_escaped = gsub("%", "%%", question_text, fixed = TRUE)
  ) %>%
  # Filter valid data
  filter(
    !is.na(fieldwork_date),
    !is.na(agreement),
    fieldwork_date >= as.Date("2021-01-01"),
    fieldwork_date <= as.Date("2025-12-31"),
    agreement >= 0,
    agreement <= 100,
    !str_detect(question_group, "^ungrouped_")
  )

print(sprintf("✅ Processed data: %d questions in %d groups", 
              nrow(grouped_data), 
              length(unique(grouped_data$question_group))))

# Get group statistics
group_stats <- grouped_data %>%
  group_by(question_group) %>%
  summarise(
    n_questions = n(),
    n_countries = n_distinct(country_clean),
    n_organizations = n_distinct(survey_organisation),
    n_timepoints = n_distinct(fieldwork_date),
    date_span = as.numeric(max(fieldwork_date) - min(fieldwork_date)),
    mean_agreement = mean(agreement, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  filter(
    n_questions >= 3,
    n_timepoints >= 2,
    date_span >= 30
  ) %>%
  arrange(desc(n_questions))

print(sprintf("📈 Found %d groups with sufficient data", nrow(group_stats)))

# Color palette
unique_countries <- unique(grouped_data$country_clean)
colors_countries <- colorRampPalette(RColorBrewer::brewer.pal(12, "Set3"))(length(unique_countries))
names(colors_countries) <- unique_countries

# NEW APPROACH: Create visualization with explicit question tracking
create_group_visualization <- function(group_name, data) {
  
  group_data <- data %>% 
    filter(question_group == group_name)
  
  if (nrow(group_data) < 3) return(NULL)
  
  # Calculate weighted average
  group_weighted_avg <- group_data %>%
    filter(!is.na(agreement), !is.na(n_respondents), n_respondents > 0) %>%
    summarise(
      weighted_agreement = sum(agreement * n_respondents) / sum(n_respondents),
      .groups = "drop"
    ) %>%
    pull(weighted_agreement)
  
  # CRITICAL CHANGE: Create hover data BEFORE aggregation
  # This ensures we have the full question text for each point
  hover_data <- group_data %>%
    select(country_clean, fieldwork_date, agreement, neutral, disagreement,
           n_respondents, survey_organisation, question_text_escaped) %>%
    group_by(country_clean, fieldwork_date) %>%
    # For each country-date combination, aggregate the data
    summarise(
      agreement = mean(agreement, na.rm = TRUE),
      neutral = mean(neutral, na.rm = TRUE),
      disagreement = mean(disagreement, na.rm = TRUE),
      n_questions = n(),
      n_surveys = n_distinct(survey_organisation),
      total_sample_size = sum(n_respondents, na.rm = TRUE),
      organizations = paste(unique(survey_organisation), collapse = "; "),
      # Combine all question texts
      questions_list = list(unique(question_text_escaped)),
      .groups = "drop"
    ) %>%
    # Create hover text for each point
    mutate(
      hover_text = map_chr(questions_list, function(q_list) {
        questions_formatted <- paste(q_list, collapse = "\n\n")
        # Truncate if too long but keep full questions when possible
        if (nchar(questions_formatted) > 800) {
          questions_formatted <- paste0(
            substr(questions_formatted, 1, 800),
            "...\n[", length(q_list), " questions total]"
          )
        }
        questions_formatted
      }),
      # Create the full hover content
      hover_content = paste0(
        "Questions: ", n_questions, "<br>",
        "Surveys: ", n_surveys, "<br>",
        "Orgs: ", str_trunc(organizations, 50), "<br>",
        "Sample: ", format(total_sample_size, big.mark = ","), "<br><br>",
        "<b>Survey Questions:</b><br>",
        gsub("\n", "<br>", hover_text)
      )
    ) %>%
    arrange(fieldwork_date) %>%
    filter(!is.na(agreement), agreement >= 0, agreement <= 100)
  
  if (nrow(hover_data) < 2) return(NULL)
  
  # Create the plot
  p <- plot_ly(source = "scatter_plot") %>%
    layout(
      title = list(
        text = paste0("<b>", str_replace_all(group_name, "_", " "), "</b><br>",
                     "<sub>Public Opinion Trends Over Time (", nrow(hover_data), " data points)</sub>"),
        x = 0.5,
        font = list(size = 16)
      ),
      xaxis = list(
        title = "Date",
        showgrid = TRUE,
        gridwidth = 1,
        gridcolor = "#E5E5E5",
        tickformat = "%b %Y"
      ),
      yaxis = list(
        title = "Agreement (%)",
        range = c(0, 100),
        showgrid = TRUE,
        gridwidth = 1,
        gridcolor = "#E5E5E5"
      ),
      hovermode = "closest",
      plot_bgcolor = "white",
      paper_bgcolor = "white",
      font = list(family = "Arial, sans-serif"),
      legend = list(
        orientation = "v",
        x = 1.02,
        y = 1,
        bgcolor = "rgba(255,255,255,0.8)",
        bordercolor = "#CCCCCC",
        borderwidth = 1
      ),
      margin = list(r = 150, b = 100)
    )
  
  # Add traces for each country
  for (country in unique(hover_data$country_clean)) {
    country_data <- hover_data %>% 
      filter(country_clean == country) %>%
      arrange(fieldwork_date)
    
    if (nrow(country_data) >= 1) {
      # Calculate marker sizes
      marker_sizes <- pmax(6, pmin(20, 6 + (country_data$total_sample_size / 500)))
      
      # Create hover text as a simple vector
      hover_text_vec <- paste0(
        "<b>", country, "</b><br>",
        "Date: ", format(country_data$fieldwork_date, "%B %Y"), "<br>",
        "Agreement: ", round(country_data$agreement, 1), "%<br>",
        "Sample Size: ", format(country_data$total_sample_size, big.mark = ","), "<br>",
        "Questions: ", country_data$n_questions, "<br>",
        "Surveys: ", country_data$n_surveys, "<br>",
        "Organizations: ", str_trunc(country_data$organizations, 50), "<br><br>",
        "<b>Survey Questions:</b><br>",
        gsub("\n", "<br>", country_data$hover_text)
      )
      
      p <- p %>%
        add_trace(
          x = country_data$fieldwork_date,
          y = country_data$agreement,
          type = "scatter",
          mode = "markers",
          name = country,
          marker = list(size = marker_sizes, opacity = 0.8, color = colors_countries[country]),
          hoverinfo = "text",
          hovertext = hover_text_vec
        )
    }
  }
  
  # Add weighted average line
  if (!is.na(group_weighted_avg) && group_weighted_avg > 0) {
    date_range <- range(hover_data$fieldwork_date, na.rm = TRUE)
    p <- p %>%
      add_trace(
        x = date_range,
        y = c(group_weighted_avg, group_weighted_avg),
        type = "scatter",
        mode = "lines",
        line = list(
          color = "#FF6B6B",
          width = 3,
          dash = "solid"
        ),
        name = paste0("Weighted Average (", round(group_weighted_avg, 1), "%)"),
        showlegend = TRUE,
        hovertemplate = paste0(
          "<b>Weighted Average</b><br>",
          "Agreement: ", round(group_weighted_avg, 1), "%<br>",
          "<extra></extra>"
        )
      )
  }
  
  # Add sample question as annotation
  sample_q <- hover_data$questions_list[[1]][1]
  if (!is.null(sample_q) && !is.na(sample_q)) {
    p <- p %>%
      layout(
        annotations = list(
          list(
            text = paste0("Sample: ", str_trunc(sample_q, 200)),
            showarrow = FALSE,
            x = 0,
            y = -0.2,
            xref = "paper",
            yref = "paper",
            xanchor = "left",
            yanchor = "top",
            font = list(size = 10, color = "#666666")
          )
        )
      )
  }
  
  return(p)
}

# Create visualizations
print("🎨 Creating visualizations with enhanced hover text...")

groups_to_plot <- group_stats$question_group
total_groups <- length(groups_to_plot)
successful_plots <- 0

for (i in seq_along(groups_to_plot)) {
  group_name <- groups_to_plot[i]
  
  cat(sprintf("Creating plot %d/%d: %s\n", i, total_groups, group_name))
  
  tryCatch({
    plot <- create_group_visualization(group_name, grouped_data)
    
    if (!is.null(plot)) {
      safe_name <- str_replace_all(group_name, "[^A-Za-z0-9_]", "_")
      file_name <- paste0("visualizations_grouped/group_", safe_name, ".html")
      
      htmlwidgets::saveWidget(
        plot,
        file = file_name,
        selfcontained = TRUE,
        title = paste("AI Polling:", str_replace_all(group_name, "_", " "))
      )
      
      successful_plots <- successful_plots + 1
      cat(sprintf("✅ Saved: %s\n", basename(file_name)))
    } else {
      cat(sprintf("⚠️ Skipped %s (insufficient data)\n", group_name))
    }
  }, error = function(e) {
    cat(sprintf("❌ Failed to create plot for %s: %s\n", group_name, e$message))
  })
}

# Create improved overview dashboard
print("📊 Creating overview dashboard...")

overview_stats <- group_stats %>%
  head(15) %>%
  mutate(
    group_name_short = str_trunc(str_replace_all(question_group, "_", " "), 40)
  )

overview_plot <- plot_ly(
  data = overview_stats,
  x = ~reorder(group_name_short, mean_agreement),
  y = ~mean_agreement,
  type = "bar",
  source = "overview_bars",
  marker = list(
    color = ~mean_agreement,
    colorscale = "RdYlBu",
    reversescale = TRUE,
    showscale = TRUE,
    colorbar = list(title = "Agreement %")
  ),
  hovertemplate = paste0(
    "<b>%{x}</b><br>",
    "Agreement: %{y:.1f}%<br>",
    "Questions: ", overview_stats$n_questions, "<br>",
    "Countries: ", overview_stats$n_countries, "<br>",
    "Organizations: ", overview_stats$n_organizations, "<br>",
    "Time Points: ", overview_stats$n_timepoints, "<br>",
    "File: group_", str_replace_all(overview_stats$question_group, "[^A-Za-z0-9_]", "_"), ".html<br>",
    "<extra></extra>"
  ),
  customdata = ~question_group
) %>%
  layout(
    title = list(
      text = "<b>AI Polling Question Groups</b><br><sub>Ordered by Level of Agreement</sub>",
      x = 0.5,
      font = list(size = 18)
    ),
    xaxis = list(
      title = "Question Group",
      tickangle = -45
    ),
    yaxis = list(
      title = "Level of Agreement (%)",
      range = c(0, 100)
    ),
    plot_bgcolor = "white",
    paper_bgcolor = "white",
    font = list(family = "Arial, sans-serif"),
    margin = list(b = 200)
  )

# Save overview with enhanced hover information
htmlwidgets::saveWidget(
  overview_plot,
  file = "visualizations_grouped/overview_dashboard.html",
  selfcontained = TRUE,
  title = "AI Polling Groups Overview"
)

# Create improved index HTML
index_content <- paste0('
<!DOCTYPE html>
<html>
<head>
    <title>AI Polling Data - Grouped Questions Analysis</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            margin: 0; 
            padding: 40px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header { 
            text-align: center; 
            margin-bottom: 40px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header h1 { margin: 0; font-size: 2.5em; font-weight: 700; }
        .header h2 { margin: 10px 0; font-size: 1.5em; font-weight: 400; }
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin: 40px 0; 
        }
        .stat-box { 
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 30px 20px; 
            border-radius: 15px; 
            text-align: center;
            box-shadow: 0 10px 20px rgba(240, 147, 251, 0.3);
        }
        .stat-box h3 { margin: 0; font-size: 2.5em; font-weight: 700; }
        .stat-box p { margin: 10px 0 0 0; font-size: 1.1em; opacity: 0.9; }
        .dashboard-link {
            text-align: center; 
            margin: 40px 0;
            padding: 20px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            border-radius: 15px;
        }
        .dashboard-link a { 
            color: white; 
            text-decoration: none; 
            font-size: 1.3em; 
            font-weight: 600;
        }
        .dashboard-link a:hover { text-decoration: underline; }
        .plot-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); 
            gap: 25px; 
            margin-top: 40px; 
        }
        .plot-card { 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border: 1px solid #f0f0f0;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .plot-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }
        .plot-card h3 { 
            margin-top: 0; 
            color: #333;
            font-size: 1.2em;
            line-height: 1.4;
        }
        .plot-card a { 
            text-decoration: none; 
            color: #667eea;
            font-weight: 600;
        }
        .plot-card a:hover { 
            color: #764ba2;
            text-decoration: underline; 
        }
        .plot-meta {
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            font-size: 0.9em;
            color: #666;
        }
        .footer {
            text-align: center; 
            margin-top: 60px; 
            padding-top: 30px;
            border-top: 2px solid #f0f0f0;
            color: #888;
        }
        .footer a { color: #667eea; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Public Opinion Polling</h1>
            <h2>Semantic Question Groups Analysis</h2>
            <p style="color: #666; font-size: 1.1em;">Interactive visualizations showing how public opinion on AI evolves across time and countries</p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <h3>', nrow(grouped_data), '</h3>
                <p>Total Questions</p>
            </div>
            <div class="stat-box">
                <h3>', nrow(group_stats), '</h3>
                <p>Question Groups</p>
            </div>
            <div class="stat-box">
                <h3>', successful_plots, '</h3>
                <p>Visualizations</p>
            </div>
            <div class="stat-box">
                <h3>', length(unique(grouped_data$country_clean)), '</h3>
                <p>Countries</p>
            </div>
        </div>
        
        <div class="dashboard-link">
            <h3>📊 <a href="overview_dashboard.html" target="_blank">Interactive Overview Dashboard</a></h3>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Explore all question groups and their statistics</p>
        </div>
        
        <div class="plot-grid">
')

# Add cards for individual plots
plot_files <- list.files("visualizations_grouped", pattern = "^group_.*\\.html$")

for (file in sort(plot_files)) {
  group_name_raw <- str_extract(file, "(?<=group_).*(?=\\.html)")
  group_name_clean <- str_replace_all(group_name_raw, "_", " ")
  
  # Find matching group stats
  group_info <- group_stats %>% 
    filter(str_replace_all(question_group, "[^A-Za-z0-9_]", "_") == group_name_raw) %>%
    slice(1)
  
  if (nrow(group_info) == 0) {
    # Try fuzzy match
    group_info <- group_stats %>% 
      filter(str_detect(str_replace_all(question_group, "[^A-Za-z0-9_]", "_"), 
                        fixed(str_sub(group_name_raw, 1, 20)))) %>%
      slice(1)
  }
  
  if (nrow(group_info) > 0) {
    index_content <- paste0(index_content, '
        <div class="plot-card">
            <h3><a href="', file, '" target="_blank">', str_trunc(group_name_clean, 60), '</a></h3>
            <div class="plot-meta">
                <div><strong>📊 Questions:</strong> ', group_info$n_questions, '</div>
                <div><strong>🌍 Countries:</strong> ', group_info$n_countries, '</div>
                <div><strong>🏢 Organizations:</strong> ', group_info$n_organizations, '</div>
                <div><strong>📈 Agreement:</strong> ', round(group_info$mean_agreement, 1), '%</div>
                <div><strong>⏱️ Timepoints:</strong> ', group_info$n_timepoints, '</div>
            </div>
        </div>
    ')
  }
}

index_content <- paste0(index_content, '
        </div>
        
        <div class="footer">
            <p><strong>Generated on ', format(Sys.Date(), "%B %d, %Y"), '</strong></p>
            <p>Data spans ', min(grouped_data$fieldwork_date, na.rm = TRUE), ' to ', max(grouped_data$fieldwork_date, na.rm = TRUE), '</p>
            <p>🔗 <a href="https://docs.google.com/spreadsheets/d/1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE" target="_blank">View Raw Data in Google Sheets</a></p>
        </div>
    </div>
</body>
</html>
')

# Save improved index
writeLines(index_content, "visualizations_grouped/index.html")

# Final summary
cat("\n🎉 Enhanced Visualization Summary:\n")
cat(sprintf("✅ Question groups with sufficient data: %d\n", nrow(group_stats)))
cat(sprintf("✅ Successful visualizations created: %d\n", successful_plots))
cat(sprintf("✅ Questions visualized: %d\n", nrow(grouped_data)))
cat(sprintf("✅ Countries included: %d\n", length(unique(grouped_data$country_clean))))
cat(sprintf("✅ Date range: %s to %s\n", min(grouped_data$fieldwork_date, na.rm = TRUE), max(grouped_data$fieldwork_date, na.rm = TRUE)))
cat("\n📁 Enhanced files created:\n")
cat("   • index.html (beautiful main dashboard)\n")
cat("   • overview_dashboard.html (interactive statistics)\n")
cat(sprintf("   • %d individual group trend visualizations\n", successful_plots))
cat("\n🌐 Open visualizations_grouped/index.html to explore your data!\n")