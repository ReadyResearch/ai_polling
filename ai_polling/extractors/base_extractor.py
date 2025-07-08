"""Abstract base class for document extractors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any

from ..core.models import PollingQuestion


class BaseExtractor(ABC):
    """Abstract base class for document extractors."""
    
    def __init__(self, cache_dir: Path):
        """Initialize extractor with cache directory."""
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def extract_from_file(self, file_path: Path) -> List[PollingQuestion]:
        """Extract polling questions from a file.
        
        Args:
            file_path: Path to the file to extract from
            
        Returns:
            List of validated PollingQuestion objects
            
        Raises:
            ExtractionError: If extraction fails
        """
        pass
    
    @abstractmethod
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this extractor can handle the given file type.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if this extractor can handle the file, False otherwise
        """
        pass
    
    def extract_from_directory(self, directory: Path) -> List[PollingQuestion]:
        """Extract from all compatible files in a directory.
        
        Args:
            directory: Directory containing files to extract from
            
        Returns:
            List of all extracted PollingQuestion objects
        """
        all_questions = []
        
        for file_path in directory.iterdir():
            if file_path.is_file() and self.can_handle_file(file_path):
                try:
                    questions = self.extract_from_file(file_path)
                    # Add source file metadata
                    for question in questions:
                        question.source_file = file_path.name
                    all_questions.extend(questions)
                except Exception as e:
                    # Log error but continue with other files
                    print(f"Failed to extract from {file_path.name}: {e}")
                    continue
        
        return all_questions