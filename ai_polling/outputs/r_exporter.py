"""Export polling data for R analysis."""

import json
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import pandas as pd

from ..core.models import PollingQuestion, PollingDataset
from ..core.config import get_config
from ..core.exceptions import RExportError
from ..core.logger import get_logger


class RExporter:
    """Export polling data in formats optimized for R analysis."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize R exporter.
        
        Args:
            output_dir: Directory for R exports (uses config default if not provided)
        """
        config = get_config()
        self.output_dir = Path(output_dir or config.output.r_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
    
    def export_dataset(self, dataset: PollingDataset, name: str = "polling_data") -> dict:
        """Export a complete dataset for R.
        
        Args:
            dataset: PollingDataset to export
            name: Base name for output files
            
        Returns:
            Dictionary with paths to created files
        """
        return self.export_questions(dataset.questions, name)
    
    def export_questions(self, questions: List[PollingQuestion], name: str = "polling_data") -> dict:
        """Export questions to multiple R-friendly formats.
        
        Args:
            questions: List of PollingQuestion objects
            name: Base name for output files
            
        Returns:
            Dictionary with paths to created files
        """
        if not questions:
            raise RExportError("No questions to export")
        
        self.logger.info(f"Exporting {len(questions)} questions for R analysis...")
        
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Convert to DataFrame
            df = self._questions_to_dataframe(questions)
            
            # Export files
            files_created = {}
            
            # 1. CSV (most compatible)
            csv_path = self.output_dir / f"{name}_{timestamp}.csv"
            df.to_csv(csv_path, index=False)
            files_created['csv'] = csv_path
            
            # 2. RDS (native R format) - if R is available
            rds_path = self.output_dir / f"{name}_{timestamp}.rds"
            if self._save_as_rds(df, rds_path):
                files_created['rds'] = rds_path
            
            # 3. JSON (for flexibility)
            json_path = self.output_dir / f"{name}_{timestamp}.json"
            self._save_as_json(questions, json_path)
            files_created['json'] = json_path
            
            # 4. R script with data loading function
            r_script_path = self.output_dir / f"load_{name}.R"
            self._create_r_script(files_created, r_script_path, name)
            files_created['r_script'] = r_script_path
            
            # 5. Latest symlinks (so R can always find most recent data)
            self._create_latest_links(files_created, name)
            
            # 6. Summary statistics for R
            summary_path = self.output_dir / f"{name}_summary_{timestamp}.csv"
            self._create_summary_file(questions, summary_path)
            files_created['summary'] = summary_path
            
            self.logger.info(f"✅ Exported {len(files_created)} files to {self.output_dir}")
            
            return files_created
            
        except Exception as e:
            raise RExportError(f"Failed to export for R: {e}")
    
    def _questions_to_dataframe(self, questions: List[PollingQuestion]) -> pd.DataFrame:
        """Convert questions to pandas DataFrame optimized for R."""
        data = []
        
        for question in questions:
            # Convert to dict
            question_dict = question.dict()
            
            # R-friendly formatting
            question_dict['category'] = question_dict['category']  # Keep as string
            
            # Convert dates to strings (R will parse them)
            if question_dict.get('fieldwork_date'):
                question_dict['fieldwork_date'] = question_dict['fieldwork_date'].strftime('%Y-%m-%d')
            
            if question_dict.get('extraction_date'):
                question_dict['extraction_date'] = question_dict['extraction_date'].strftime('%Y-%m-%d')
            
            # Ensure numeric columns are properly typed
            for col in ['agreement', 'neutral', 'disagreement', 'n_respondents']:
                if question_dict.get(col) is not None:
                    question_dict[col] = float(question_dict[col])
            
            data.append(question_dict)
        
        df = pd.DataFrame(data)
        
        # R-friendly column names (no dots, underscores OK)
        df.columns = [col.replace('.', '_') for col in df.columns]
        
        # Reorder columns for R analysis convenience
        column_order = [
            'question_text', 'category', 'survey_organisation', 'country',
            'fieldwork_date', 'agreement', 'neutral', 'disagreement',
            'n_respondents', 'response_scale', 'notes', 'source_file',
            'extraction_date'
        ]
        
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns + [col for col in df.columns if col not in existing_columns]]
        
        return df
    
    def _save_as_rds(self, df: pd.DataFrame, rds_path: Path) -> bool:
        """Save DataFrame as RDS file using R (if available)."""
        try:
            # Create temporary CSV
            temp_csv = self.output_dir / "temp_for_rds.csv"
            df.to_csv(temp_csv, index=False)
            
            # R script to convert CSV to RDS
            r_code = f"""
            library(readr)
            data <- read_csv("{temp_csv}", show_col_types = FALSE)
            
            # Convert date columns
            if ("fieldwork_date" %in% colnames(data)) {{
                data$fieldwork_date <- as.Date(data$fieldwork_date)
            }}
            
            # Convert factors for categorical data
            if ("category" %in% colnames(data)) {{
                data$category <- as.factor(data$category)
            }}
            if ("survey_organisation" %in% colnames(data)) {{
                data$survey_organisation <- as.factor(data$survey_organisation)
            }}
            if ("country" %in% colnames(data)) {{
                data$country <- as.factor(data$country)
            }}
            
            # Save as RDS
            saveRDS(data, "{rds_path}")
            cat("RDS file saved successfully\\n")
            """
            
            # Run R script
            result = subprocess.run(
                ["Rscript", "-e", r_code],
                capture_output=True,
                text=True
            )
            
            # Clean up temp file
            temp_csv.unlink(missing_ok=True)
            
            if result.returncode == 0:
                self.logger.debug(f"✅ Created RDS file: {rds_path}")
                return True
            else:
                self.logger.warning(f"Failed to create RDS file: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Failed to create RDS file: {e}")
            return False
    
    def _save_as_json(self, questions: List[PollingQuestion], json_path: Path) -> None:
        """Save questions as JSON for flexibility."""
        data = [question.dict() for question in questions]
        
        # Convert dates to strings for JSON serialization
        for item in data:
            if item.get('fieldwork_date'):
                item['fieldwork_date'] = item['fieldwork_date'].strftime('%Y-%m-%d')
            if item.get('extraction_date'):
                item['extraction_date'] = item['extraction_date'].strftime('%Y-%m-%d %H:%M:%S')
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _create_r_script(self, files_created: dict, r_script_path: Path, name: str) -> None:
        """Create R script with convenient data loading functions."""
        
        r_code = f'''# AI Polling Data Loading Script
# Generated by ai-polling pipeline on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

library(readr)
library(dplyr)
library(lubridate)

# Load polling data
load_{name}_data <- function(format = "csv") {{
  
  if (format == "csv") {{
    # Load from CSV (most compatible)
    data <- read_csv("{files_created.get('csv', '')}", show_col_types = FALSE)
    
    # Convert date columns
    if ("fieldwork_date" %in% colnames(data)) {{
      data$fieldwork_date <- as.Date(data$fieldwork_date)
    }}
    
    # Convert to factors for better R analysis
    factor_cols <- c("category", "survey_organisation", "country")
    for (col in factor_cols) {{
      if (col %in% colnames(data)) {{
        data[[col]] <- as.factor(data[[col]])
      }}
    }}
    
    return(data)
    
  }} else if (format == "rds") {{
    # Load from RDS (native R format)
    if (file.exists("{files_created.get('rds', '')}")) {{
      return(readRDS("{files_created.get('rds', '')}"))
    }} else {{
      warning("RDS file not found, falling back to CSV")
      return(load_{name}_data("csv"))
    }}
  }}
}}

# Convenience function to load latest data
load_latest_{name} <- function() {{
  return(load_{name}_data())
}}

# Filter functions for common analyses
get_ai_regulation_questions <- function(data = NULL) {{
  if (is.null(data)) data <- load_latest_{name}()
  return(data %>% filter(category == "AI_Regulation"))
}}

get_questions_by_organization <- function(org, data = NULL) {{
  if (is.null(data)) data <- load_latest_{name}()
  return(data %>% filter(survey_organisation == org))
}}

get_questions_by_country <- function(country, data = NULL) {{
  if (is.null(data)) data <- load_latest_{name}()
  return(data %>% filter(country == country))
}}

# Summary function
summarize_{name} <- function(data = NULL) {{
  if (is.null(data)) data <- load_latest_{name}()
  
  cat("=== AI POLLING DATA SUMMARY ===\\n")
  cat("Total questions:", nrow(data), "\\n")
  cat("Organizations:", length(unique(data$survey_organisation)), "\\n")
  cat("Countries:", length(unique(data$country)), "\\n")
  cat("Date range:", min(data$fieldwork_date, na.rm = TRUE), "to", 
      max(data$fieldwork_date, na.rm = TRUE), "\\n")
  
  cat("\\nQuestions by category:\\n")
  print(table(data$category))
  
  cat("\\nQuestions by organization:\\n")
  print(table(data$survey_organisation))
  
  return(invisible(data))
}}

# Example usage:
# data <- load_latest_{name}()
# ai_reg <- get_ai_regulation_questions()
# summarize_{name}()

cat("AI Polling data loading functions ready!\\n")
cat("Use load_latest_{name}() to load the data\\n")
cat("Use summarize_{name}() for a quick overview\\n")
'''
        
        with open(r_script_path, 'w') as f:
            f.write(r_code)
    
    def _create_latest_links(self, files_created: dict, name: str) -> None:
        """Create 'latest' symlinks/copies for easy R access."""
        
        for file_type, file_path in files_created.items():
            if file_type in ['csv', 'rds', 'json']:
                latest_path = self.output_dir / f"{name}_latest.{file_type}"
                
                try:
                    # Remove existing link/file
                    latest_path.unlink(missing_ok=True)
                    
                    # Create symlink (or copy if symlinks not supported)
                    try:
                        latest_path.symlink_to(file_path.name)
                    except OSError:
                        # Fallback to copying if symlinks not supported
                        import shutil
                        shutil.copy2(file_path, latest_path)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to create latest link for {file_type}: {e}")
    
    def _create_summary_file(self, questions: List[PollingQuestion], summary_path: Path) -> None:
        """Create summary statistics file for R."""
        from ..processors.aggregator import get_summary_statistics
        
        stats = get_summary_statistics(questions)
        
        # Convert to R-friendly format
        summary_data = []
        
        # Basic stats
        summary_data.append({'metric': 'total_questions', 'value': stats.get('total_questions', 0)})
        summary_data.append({'metric': 'unique_organizations', 'value': stats.get('unique_organizations', 0)})
        summary_data.append({'metric': 'unique_countries', 'value': stats.get('unique_countries', 0)})
        
        # Agreement stats
        if stats.get('agreement_statistics'):
            agree_stats = stats['agreement_statistics']
            summary_data.extend([
                {'metric': 'mean_agreement', 'value': agree_stats['mean']},
                {'metric': 'median_agreement', 'value': agree_stats['median']},
                {'metric': 'min_agreement', 'value': agree_stats['min']},
                {'metric': 'max_agreement', 'value': agree_stats['max']},
            ])
        
        # Category breakdown
        if stats.get('category_breakdown'):
            for category, count in stats['category_breakdown'].items():
                # Handle both enum and string categories
                cat_str = category.value if hasattr(category, 'value') else str(category)
                summary_data.append({'metric': f'count_{cat_str.lower()}', 'value': count})
        
        # Save as CSV
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv(summary_path, index=False)
    
    def create_r_package_structure(self, questions: List[PollingQuestion]) -> Path:
        """Create a basic R package structure for the polling data.
        
        Args:
            questions: List of questions to include in package
            
        Returns:
            Path to created package directory
        """
        package_name = "aipolling"
        package_dir = self.output_dir / package_name
        
        # Create package structure
        (package_dir / "R").mkdir(parents=True, exist_ok=True)
        (package_dir / "data").mkdir(exist_ok=True)
        (package_dir / "man").mkdir(exist_ok=True)
        
        # Save data
        data_files = self.export_questions(questions, "polling_data")
        
        # Create DESCRIPTION file
        description = f'''Package: {package_name}
Title: AI Public Opinion Polling Data
Version: 0.1.0
Authors@R: person("AI Polling", "Team", email = "noetel@gmail.com", role = c("aut", "cre"))
Description: Polling data about public opinion on AI regulation, risks, and sentiment.
License: MIT
Encoding: UTF-8
LazyData: true
Roxygen: list(markdown = TRUE)
RoxygenNote: 7.0.0
Imports: 
    dplyr,
    readr,
    lubridate
'''
        
        with open(package_dir / "DESCRIPTION", 'w') as f:
            f.write(description)
        
        # Create main R functions file
        r_functions = '''#' Load AI Polling Data
#'
#' Load the latest AI polling dataset
#'
#' @return A data frame with polling questions and results
#' @export
load_polling_data <- function() {
  # Implementation would load the bundled data
  # For now, this is a placeholder
  return(data.frame())
}

#' Get AI Regulation Questions
#'
#' Filter dataset to AI regulation questions only
#'
#' @param data Optional data frame, loads latest if NULL
#' @return Filtered data frame
#' @export
get_ai_regulation_questions <- function(data = NULL) {
  if (is.null(data)) data <- load_polling_data()
  return(data[data$category == "AI_Regulation", ])
}
'''
        
        with open(package_dir / "R" / "data_functions.R", 'w') as f:
            f.write(r_functions)
        
        self.logger.info(f"✅ Created R package structure at {package_dir}")
        
        return package_dir