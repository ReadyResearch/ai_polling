# Configuration file for AI Polling Data Pipeline

# API Configuration
# Get your Google API key from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY <- Sys.getenv("GOOGLE_API_KEY")

if (GOOGLE_API_KEY == "") {
  stop("GOOGLE_API_KEY environment variable not set. Please set it with your Google API key.")
}


# Processing Configuration
MAX_FILE_SIZE_CHARS <- 50000  # Maximum characters per file to process
MAX_CACHE_AGE_HOURS <- 24     # How long to keep cached results
MAX_API_RETRIES <- 3          # Number of times to retry failed API calls

# Model Configuration
EXTRACTION_MODEL <- "gemini-2.5-flash"  # Fast, cost-effective model for extraction
ANALYSIS_MODEL <- "gemini-2.5-pro"   # More capable model for complex analysis

# File Paths
MARKDOWN_DIR <- "polling_markdown"
CACHE_DIR <- "cache"
EXTRACTED_DATA_DIR <- "extracted_data"
LOGS_DIR <- "logs"

# Visualization Configuration
PLOT_THEME <- "minimal"
DEFAULT_COLORS <- c("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                   "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf")

# Data Validation Rules
REQUIRED_FIELDS <- c("Question_Text", "Response_Scale", "Category", "Agreement",
                    "Country", "Survey_Organisation", "Fieldwork_Date")

VALID_CATEGORIES <- c("AI_Regulation", "AI_Risk_Concern", "Job_Displacement",
                     "Extinction_Risk", "AI_Sentiment", "Other")

# Quality Checks
MIN_RESPONDENTS <- 100        # Minimum sample size to include
MAX_AGREEMENT_PERCENT <- 100  # Maximum valid percentage
MIN_AGREEMENT_PERCENT <- 0    # Minimum valid percentage
