"""AI Polling Data Extraction Pipeline.

A modern, robust pipeline for extracting polling data about AI public opinion
from various document formats and uploading to Google Sheets and R.
"""

__version__ = "0.1.0"

from .core.models import PollingQuestion, PollingDataset
from .extractors.pdf_extractor import PDFExtractor
from .processors.validator import validate_polling_data
from .outputs.sheets_uploader import SheetsUploader
from .outputs.r_exporter import RExporter

__all__ = [
    "PollingQuestion",
    "PollingDataset", 
    "PDFExtractor",
    "validate_polling_data",
    "SheetsUploader",
    "RExporter",
]