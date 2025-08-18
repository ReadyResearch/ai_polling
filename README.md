# AI Polling Data Extraction Pipeline
---

## 📊 [**VIEW INTERACTIVE VISUALIZATIONS**](https://readyresearch.github.io/ai_polling/visualizations_grouped/index.html) 📊

*Click above to explore AI public opinion trends across 40+ countries and 1000+ polling questions*

A modern Python pipeline for extracting and analyzing AI public opinion polling data from PDFs and documents.

## Overview

This pipeline extracts polling questions from research documents, validates the data, and exports it to Google Sheets and R-friendly formats for analysis. Built with type safety, robust error handling, and modern Python practices.

## Features

- **Type-safe extraction** with Pydantic models
- **Multiple extractors**: PDF (via Google Gemini), Excel/CSV
- **Smart caching** to minimize API costs
- **Data validation** with quality scoring
- **Google Sheets integration** for collaboration
- **R export** with auto-generated loading scripts
- **Modern CLI** with Rich interface
- **Comprehensive error handling**

## Installation

```bash
# Clone repository
git clone <repository-url>
cd ai_polling

# Install package
pip install -e .

# Or install dependencies manually
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file with your Google API key:
```bash
GOOGLE_API_KEY=your-gemini-api-key-here
```

2. The pipeline uses `config.yaml` for settings - API key is loaded from environment variable
3. For Google Sheets integration, ensure you have Google Cloud credentials configured

## Quick Start

```bash
# Extract data from documents
ai-polling extract documents/ --output extracted_data/

# Upload to Google Sheets
ai-polling upload extracted_data/polling_data_latest.csv

# Validate data quality
ai-polling validate extracted_data/polling_data_latest.csv

# Show summary
ai-polling summary
```

## Usage

### Command Line Interface

```bash
# Extract from PDFs and Excel files
ai-polling extract source_directory/ --type pdf --type excel

# Upload to specific Google Sheet
ai-polling upload data.csv --sheet-id "your-sheet-id"

# Validate with cleaning
ai-polling validate data.csv --clean --strict

# View configuration
ai-polling config --show

# Get help
ai-polling --help
```

### Python API

```python
from ai_polling import PDFExtractor, PollingDataset, RExporter

# Extract from PDF
extractor = PDFExtractor()
questions = extractor.extract_from_file("survey.pdf")

# Create dataset
dataset = PollingDataset(questions=questions)

# Export for R
exporter = RExporter("output/")
files = exporter.export_dataset(dataset)
```

## Data Model

The pipeline extracts polling questions with these fields:

- `question_text`: Exact question wording
- `response_scale`: Available response options
- `category`: Question type (AI_Regulation, AI_Risk_Concern, etc.)
- `agreement`: Sum of positive response percentages
- `neutral`: Neutral response percentage
- `disagreement`: Sum of negative response percentages
- `n_respondents`: Sample size
- `country`: Survey location
- `survey_organisation`: Conducting organization
- `fieldwork_date`: When survey was conducted
- `notes`: Additional context

## R Integration

The pipeline generates R-ready files:

```r
# Load the auto-generated script
source("extracted_data/load_polling_data.R")

# Load latest data
data <- load_latest_polling_data()

# Quick summary
summarize_polling_data()

# Filter by category
ai_reg <- get_ai_regulation_questions()

# Filter by organization
pew_data <- get_questions_by_organization("Pew Research Center")
```

## Architecture

```
ai_polling/
├── core/           # Configuration, models, exceptions
├── extractors/     # PDF, Excel extractors
├── processors/     # Validation, aggregation
├── outputs/        # Google Sheets, R exports
└── cli.py         # Command-line interface
```

## File Types Supported

- **PDF**: Research reports, surveys (via Google Gemini)
- **Excel/CSV**: Tabular polling data
- **Output formats**: CSV, RDS, JSON, Google Sheets

## Data Quality

The pipeline includes comprehensive validation:

- Missing field detection
- Percentage sum validation
- Date format checking
- Sample size validation
- Quality scoring (0-100)

## Error Handling

- Custom exception hierarchy
- Retry logic with exponential backoff
- Graceful degradation
- Detailed error logging

## Caching

Smart caching system:
- Content-based cache keys
- Configurable cache directory
- Automatic cleanup
- Cost-effective API usage

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Format code
black ai_polling/
isort ai_polling/

# Type checking
mypy ai_polling/
```

## Configuration Reference

See `config.yaml` for all available settings:

- API configuration (model, tokens, rate limits)
- Extraction settings (batch size, retries)
- Output destinations (Google Sheets, R directory)
- Category keywords for classification

## Examples

### Extract from Multiple Sources
```bash
ai-polling extract surveys/ --type pdf --type excel --batch 3
```

### Custom Output Location
```bash
ai-polling extract docs/ --output my_analysis/
```

### Validation with Cleaning
```bash
ai-polling validate data.csv --clean --strict
```

### Configuration Management
```bash
ai-polling config --show
ai-polling config --edit
```

## Troubleshooting

### Google API Issues
- Ensure `GOOGLE_API_KEY` environment variable is set
- Check API quotas and billing
- Verify Gemini API access

### Google Sheets Issues
- Configure Google Cloud credentials
- Check spreadsheet permissions
- Verify sheet ID in config

### R Integration Issues
- Ensure R is installed and in PATH
- Install required R packages: `readr`, `dplyr`, `lubridate`
- Check file permissions

## Visualizations

The project includes interactive visualizations of the polling data:

- **Live Demo**: [View visualizations](https://readyresearch.github.io/ai_polling/visualizations_grouped/) *(if repo is public)*
- **Local Access**: Open `visualizations_grouped/index.html` in your browser
- **Overview Dashboard**: Comprehensive interactive dashboard with all question categories
- **Individual Topics**: Separate visualizations for each question category (AI regulation, risks, job displacement, etc.)

### Visualization Features

- Interactive plotly charts with hover details
- Time series analysis with trend lines
- Country-based filtering and comparison
- Professional styling and responsive design
- Self-contained HTML files for easy sharing

## Data Sources

The pipeline has processed polling data from 25+ major organizations:

- **Pew Research Center** - Multiple AI surveys 2022-2024
- **Ipsos** - Global and US-specific AI opinion tracking
- **AI Policy Institute** - Specialized AI governance polling
- **YouGov** - Cross-national AI sentiment analysis
- **Gallup** - AI workplace and societal impact studies
- **University research** - Academic AI risk perception studies
- **And many more...**

## Project Status

✅ **Complete**: Data extraction pipeline, validation, R integration, interactive visualizations
🔧 **Active**: Ongoing data updates and visualization improvements
📊 **Output**: 1000+ polling questions across 40+ countries and 30+ question categories

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## Support

- GitHub Issues: Report bugs and feature requests
- Documentation: Check inline docstrings and type hints
