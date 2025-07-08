"""Configuration management for AI Polling pipeline."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from pydantic import BaseModel, Field, field_validator

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # dotenv is optional


class APIConfig(BaseModel):
    """API configuration settings."""
    
    google_api_key: str = Field(..., description="Google API key for Gemini")
    thinking_budget: int = Field(1024, description="Thinking budget for Gemini 2.5")
    model_name: str = Field("gemini-2.5-flash", description="Gemini model to use")
    
    @field_validator("google_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "":
            raise ValueError("Google API key is required")
        return v


class ExtractionConfig(BaseModel):
    """Extraction configuration settings."""
    
    batch_size: int = Field(5, description="Number of files to process before pause")
    retry_attempts: int = Field(3, description="Number of retry attempts for failed extractions")
    rate_limit_delay: float = Field(2.0, description="Delay between batches (seconds)")
    max_output_tokens: int = Field(8192, description="Maximum tokens in model response")
    temperature: float = Field(0.0, description="Model temperature (0.0 = deterministic)")
    
    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("Batch size must be between 1 and 20")
        return v


class OutputConfig(BaseModel):
    """Output configuration settings."""
    
    google_sheet_id: str = Field(..., description="Google Sheets ID for uploads")
    sheet_tab_name: str = Field("Poll Results", description="Sheet tab name")
    r_output_dir: str = Field("extracted_data", description="Directory for R exports")
    cache_dir: str = Field("cache", description="Directory for caching")
    
    @field_validator("google_sheet_id")
    @classmethod
    def validate_sheet_id(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("Invalid Google Sheets ID")
        return v


class CategoryConfig(BaseModel):
    """Configuration for question categorization."""
    
    ai_regulation_keywords: List[str] = Field(
        default=[
            "regulation", "oversight", "governance", "government", "federal",
            "testing", "safety standards", "approval", "licensed", "regulated",
            "international cooperation", "global coordination"
        ]
    )
    
    ai_risk_keywords: List[str] = Field(
        default=[
            "risk", "danger", "harm", "threat", "worry", "concern", "afraid",
            "negative effects", "problems", "issues", "catastrophic"
        ]
    )
    
    extinction_risk_keywords: List[str] = Field(
        default=[
            "extinction", "end of humanity", "human race", "civilization",
            "existential", "species", "survival", "apocalypse"
        ]
    )
    
    job_displacement_keywords: List[str] = Field(
        default=[
            "job", "employment", "work", "unemployment", "displaced",
            "replace workers", "automation", "career", "profession"
        ]
    )


class Config(BaseModel):
    """Main configuration class."""
    
    api: APIConfig
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    output: OutputConfig
    categories: CategoryConfig = Field(default_factory=CategoryConfig)
    
    @classmethod
    def load_from_file(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file with environment variable fallbacks."""
        
        if config_path is None:
            config_path = Path("config.yaml")
        
        # Load YAML config if it exists
        config_data: Dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Environment variable fallbacks and substitution
        api_config = config_data.get("api", {})
        api_key = api_config.get("google_api_key", "")
        
        # Handle environment variable substitution
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var_name = api_key[2:-1]  # Remove ${ and }
            api_config["google_api_key"] = os.getenv(env_var_name, "")
        elif not api_key:
            api_config["google_api_key"] = os.getenv("GOOGLE_API_KEY", "")
        
        output_config = config_data.get("output", {})
        if not output_config.get("google_sheet_id"):
            # Default to the sheet ID we've been using
            output_config["google_sheet_id"] = "1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE"
        
        # Build final config
        final_config = {
            "api": api_config,
            "extraction": config_data.get("extraction", {}),
            "output": output_config,
            "categories": config_data.get("categories", {})
        }
        
        return cls(**final_config)
    
    def save_to_file(self, config_path: Path) -> None:
        """Save current configuration to YAML file."""
        
        # Don't save sensitive data to file
        config_dict = self.dict()
        config_dict["api"]["google_api_key"] = "${GOOGLE_API_KEY}"
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load_from_file()
    return _config


def reload_config(config_path: Optional[Path] = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load_from_file(config_path)
    return _config