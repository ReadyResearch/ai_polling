#!/usr/bin/env Rscript

# Interactive Plotly Visualization for AI Polling Data

library(tidyverse)
library(plotly)
library(lubridate)
library(fs)
library(htmlwidgets)
library(RColorBrewer)

source("config.R")

# Load and prepare data
load_and_prepare_data <- function() {
  data_file <- file.path(EXTRACTED_DATA_DIR, "combined_polling_data.rds")
  
  if (!file.exists(data_file)) {
    stop("Cleaned data file not found. Please run validate_data.R first.")
  }
  
  data <- readRDS(data_file)
  
  # Prepare data for visualization
  data <- data %>%
    mutate(
      Fieldwork_Date = as.Date(Fieldwork_Date),
      Fieldwork_Year = year(Fieldwork_Date),
      Fieldwork_Month = month(Fieldwork_Date),
      # Create a continuous time variable for trend lines
      time_numeric = as.numeric(Fieldwork_Date),
      # Create hover text
      hover_text = paste0(
        "<b>", Question_Text, "</b><br>",
        "Country: ", Country, "<br>",
        "Agreement: ", Agreement, "%<br>",
        "Sample Size: ", N_Respondents, "<br>",
        "Date: ", format(Fieldwork_Date, "%B %Y"), "<br>",
        "Organization: ", Survey_Organisation, "<br>",
        "Notes: ", substr(Notes, 1, 100), ifelse(nchar(Notes) > 100, "...", "")
      )
    ) %>%
    filter(!is.na(Fieldwork_Date), !is.na(Agreement))
  
  return(data)
}

# Create main visualization
create_main_visualization <- function(data) {
  
  # Define colors for countries
  countries <- unique(data$Country)
  n_countries <- length(countries)
  
  if (n_countries <= 10) {
    colors <- brewer.pal(max(3, n_countries), "Set3")
  } else {
    colors <- rainbow(n_countries)
  }
  
  names(colors) <- countries
  
  # Create base plot
  p <- plot_ly(
    data = data,
    x = ~Fieldwork_Date,
    y = ~Agreement,
    color = ~Country,
    colors = colors,
    text = ~hover_text,
    hovertemplate = "%{text}<extra></extra>",
    type = "scatter",
    mode = "markers",
    marker = list(
      size = 8,
      opacity = 0.7,
      line = list(width = 1, color = "white")
    )
  ) %>%
  layout(
    title = list(
      text = "AI Polling Data: Public Opinion Trends Over Time",
      font = list(size = 18, family = "Arial, sans-serif")
    ),
    xaxis = list(
      title = "Date",
      type = "date",
      tickformat = "%b %Y",
      showgrid = TRUE,
      gridcolor = "lightgray"
    ),
    yaxis = list(
      title = "Agreement Percentage (%)",
      range = c(0, 100),
      showgrid = TRUE,
      gridcolor = "lightgray"
    ),
    font = list(family = "Arial, sans-serif", size = 12),
    plot_bgcolor = "white",
    paper_bgcolor = "white",
    hovermode = "closest",
    legend = list(
      orientation = "v",
      x = 1.05,
      y = 1,
      bgcolor = "rgba(255,255,255,0.8)",
      bordercolor = "gray",
      borderwidth = 1
    )
  )
  
  # Skip trend lines for now to avoid data structure issues
  cat("Skipping trend lines to ensure basic visualization works\n")
  
  return(p)
}

# Create category-specific visualizations
create_category_plots <- function(data) {
  
  categories <- unique(data$Category)
  category_plots <- list()
  
  for (category in categories) {
    cat_data <- data %>% filter(Category == category)
    
    if (nrow(cat_data) > 0) {
      # Get countries for this category
      countries <- unique(cat_data$Country)
      n_countries <- length(countries)
      
      if (n_countries <= 10) {
        colors <- brewer.pal(max(3, n_countries), "Set3")
      } else {
        colors <- rainbow(n_countries)
      }
      names(colors) <- countries
      
      p <- plot_ly(
        data = cat_data,
        x = ~Fieldwork_Date,
        y = ~Agreement,
        color = ~Country,
        colors = colors,
        text = ~hover_text,
        hovertemplate = "%{text}<extra></extra>",
        type = "scatter",
        mode = "markers",
        marker = list(
          size = 8,
          opacity = 0.7,
          line = list(width = 1, color = "white")
        )
      ) %>%
      layout(
        title = list(
          text = paste("Category:", category),
          font = list(size = 16, family = "Arial, sans-serif")
        ),
        xaxis = list(
          title = "Date",
          type = "date",
          tickformat = "%b %Y",
          showgrid = TRUE,
          gridcolor = "lightgray"
        ),
        yaxis = list(
          title = "Agreement Percentage (%)",
          range = c(0, 100),
          showgrid = TRUE,
          gridcolor = "lightgray"
        ),
        font = list(family = "Arial, sans-serif", size = 12),
        plot_bgcolor = "white",
        paper_bgcolor = "white",
        hovermode = "closest",
        legend = list(
          orientation = "v",
          x = 1.05,
          y = 1,
          bgcolor = "rgba(255,255,255,0.8)",
          bordercolor = "gray",
          borderwidth = 1
        )
      )
      
      category_plots[[category]] <- p
    }
  }
  
  return(category_plots)
}

# Create summary statistics plot
create_summary_plot <- function(data) {
  
  # Calculate summary statistics by category and country
  summary_data <- data %>%
    group_by(Category, Country) %>%
    summarise(
      mean_agreement = mean(Agreement, na.rm = TRUE),
      median_agreement = median(Agreement, na.rm = TRUE),
      n_questions = n(),
      min_date = min(Fieldwork_Date, na.rm = TRUE),
      max_date = max(Fieldwork_Date, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    filter(n_questions >= 2)  # Only include combinations with multiple questions
  
  # Create heatmap
  p <- plot_ly(
    data = summary_data,
    x = ~Country,
    y = ~Category,
    z = ~mean_agreement,
    type = "heatmap",
    colorscale = "RdYlBu",
    reversescale = TRUE,
    hovertemplate = paste(
      "<b>%{y}</b><br>",
      "Country: %{x}<br>",
      "Mean Agreement: %{z:.1f}%<br>",
      "Questions: %{customdata}<br>",
      "<extra></extra>"
    ),
    customdata = ~n_questions
  ) %>%
  layout(
    title = list(
      text = "Mean Agreement by Category and Country",
      font = list(size = 18, family = "Arial, sans-serif")
    ),
    xaxis = list(
      title = "Country",
      tickangle = 45
    ),
    yaxis = list(
      title = "Category"
    ),
    font = list(family = "Arial, sans-serif", size = 12)
  )
  
  return(p)
}

# Save all visualizations
save_visualizations <- function(data) {
  cat("Creating visualizations...\n")
  
  # Create output directory
  viz_dir <- "visualizations"
  dir_create(viz_dir, recurse = TRUE)
  
  # Main visualization
  cat("Creating main plot...\n")
  main_plot <- create_main_visualization(data)
  
  # Save as HTML
  htmlwidgets::saveWidget(
    main_plot,
    file.path(viz_dir, "main_polling_trends.html"),
    selfcontained = TRUE,
    title = "AI Polling Data: Main Trends"
  )
  
  # Category-specific plots
  cat("Creating category plots...\n")
  category_plots <- create_category_plots(data)
  
  for (category in names(category_plots)) {
    filename <- paste0("category_", gsub("[^A-Za-z0-9]", "_", category), ".html")
    htmlwidgets::saveWidget(
      category_plots[[category]],
      file.path(viz_dir, filename),
      selfcontained = TRUE,
      title = paste("AI Polling Data:", category)
    )
  }
  
  # Summary heatmap
  cat("Creating summary heatmap...\n")
  summary_plot <- create_summary_plot(data)
  
  htmlwidgets::saveWidget(
    summary_plot,
    file.path(viz_dir, "summary_heatmap.html"),
    selfcontained = TRUE,
    title = "AI Polling Data: Summary Heatmap"
  )
  
  cat("All visualizations saved to:", viz_dir, "\n")
  
  return(list(
    main = main_plot,
    categories = category_plots,
    summary = summary_plot
  ))
}

# Generate data summary table
create_data_table <- function(data) {
  library(DT)
  
  # Prepare data for table
  table_data <- data %>%
    select(
      Question_Text, Country, Category, Agreement, Disagreement, Neutral,
      N_Respondents, Survey_Organisation, Fieldwork_Date, Notes
    ) %>%
    mutate(
      Question_Text = substr(Question_Text, 1, 100),  # Truncate long questions
      Notes = substr(Notes, 1, 50)  # Truncate long notes
    )
  
  # Create interactive table
  dt <- datatable(
    table_data,
    options = list(
      pageLength = 25,
      scrollX = TRUE,
      filter = "top",
      columnDefs = list(
        list(width = "300px", targets = 0),  # Question text column
        list(width = "80px", targets = 3:5)  # Percentage columns
      )
    ),
    caption = "AI Polling Data: Interactive Table",
    filter = "top"
  )
  
  return(dt)
}

# Main execution function
main <- function() {
  cat("=== AI POLLING DATA VISUALIZATION ===\n")
  
  # Load and prepare data
  data <- load_and_prepare_data()
  
  cat("Loaded", nrow(data), "records for visualization\n")
  cat("Date range:", as.character(min(data$Fieldwork_Date)), "to", as.character(max(data$Fieldwork_Date)), "\n")
  cat("Countries:", length(unique(data$Country)), "\n")
  cat("Categories:", length(unique(data$Category)), "\n")
  
  # Create and save visualizations
  plots <- save_visualizations(data)
  
  # Create interactive table
  cat("Creating interactive data table...\n")
  data_table <- create_data_table(data)
  
  # Save table
  table_file <- file.path("visualizations", "data_table.html")
  htmlwidgets::saveWidget(
    data_table,
    table_file,
    selfcontained = TRUE,
    title = "AI Polling Data: Interactive Table"
  )
  
  cat("Data table saved to:", table_file, "\n")
  
  cat("\n=== VISUALIZATION COMPLETE ===\n")
  cat("Files created in visualizations/ directory:\n")
  cat("- main_polling_trends.html (main interactive plot)\n")
  cat("- category_*.html (category-specific plots)\n")
  cat("- summary_heatmap.html (summary heatmap)\n")
  cat("- data_table.html (interactive data table)\n")
  
  # Print summary statistics
  cat("\n=== SUMMARY STATISTICS ===\n")
  cat("Overall mean agreement:", round(mean(data$Agreement, na.rm = TRUE), 1), "%\n")
  cat("Overall median agreement:", round(median(data$Agreement, na.rm = TRUE), 1), "%\n")
  
  cat("\nMean agreement by category:\n")
  category_summary <- data %>%
    group_by(Category) %>%
    summarise(
      mean_agreement = round(mean(Agreement, na.rm = TRUE), 1),
      n_questions = n(),
      .groups = "drop"
    ) %>%
    arrange(desc(mean_agreement))
  
  for (i in 1:nrow(category_summary)) {
    cat(category_summary$Category[i], ":", category_summary$mean_agreement[i], "% (", category_summary$n_questions[i], "questions)\n")
  }
  
  return(plots)
}

# Run if not interactive
if (!interactive()) {
  main()
}