"""Custom exceptions for the AI Polling pipeline."""


class AIPollingError(Exception):
    """Base exception for AI Polling pipeline errors."""
    pass


class ConfigurationError(AIPollingError):
    """Configuration-related errors."""
    pass


class ExtractionError(AIPollingError):
    """Base class for extraction-related errors."""
    pass


class APIError(ExtractionError):
    """API-related errors (rate limits, authentication, etc.)."""
    pass


class APIRateLimitError(APIError):
    """API rate limit exceeded."""
    pass


class APIAuthenticationError(APIError):
    """API authentication failed."""
    pass


class DocumentParsingError(ExtractionError):
    """Document parsing failed."""
    pass


class ValidationError(AIPollingError):
    """Data validation errors."""
    pass


class DataQualityError(ValidationError):
    """Data quality issues."""
    pass


class CacheError(AIPollingError):
    """Caching-related errors."""
    pass


class OutputError(AIPollingError):
    """Output/export-related errors."""
    pass


class SheetsUploadError(OutputError):
    """Google Sheets upload errors."""
    pass


class RExportError(OutputError):
    """R export errors."""
    pass