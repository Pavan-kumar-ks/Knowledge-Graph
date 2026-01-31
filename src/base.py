"""
Base classes and interfaces for pipeline components.
Provides abstraction for reusable pipeline architecture.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

T = TypeVar('T')


class PipelineComponent(ABC, Generic[T]):
    """
    Base class for all pipeline components.
    Enforces consistent interface and logging.
    """
    
    def __init__(self, name: str):
        """
        Initialize pipeline component.
        
        Args:
            name: Component name for logging
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    @abstractmethod
    def execute(self, input_data: Any) -> T:
        """
        Execute the component logic.
        
        Args:
            input_data: Input data for processing
            
        Returns:
            Processed output
        """
        pass
    
    def run(self, input_data: Any) -> T:
        """
        Wrapper method with logging and error handling.
        
        Args:
            input_data: Input data for processing
            
        Returns:
            Processed output
            
        Raises:
            Exception: If execution fails
        """
        self.start_time = datetime.now()
        self.logger.info(f"🚀 Starting {self.name}...")
        
        try:
            result = self.execute(input_data)
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()
            self.logger.info(f"✅ {self.name} completed in {duration:.2f}s")
            return result
        except Exception as e:
            self.logger.error(f"❌ {self.name} failed: {e}", exc_info=True)
            raise
    
    def get_duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class DataValidator(ABC):
    """
    Base class for data validation components.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.errors = []
    
    @abstractmethod
    def validate(self, data: Any) -> bool:
        """
        Validate data.
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def get_errors(self):
        """Get validation errors."""
        return self.errors
    
    def clear_errors(self):
        """Clear validation errors."""
        self.errors = []
