"""
Data validation utilities for the pipeline.
"""

from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_dict_keys(data: Dict, required_keys: List[str]) -> bool:
    """
    Validate that dictionary contains all required keys.
    
    Args:
        data: Dictionary to validate
        required_keys: List of required keys
        
    Returns:
        True if all keys present
        
    Raises:
        ValidationError: If required keys are missing
    """
    missing_keys = set(required_keys) - set(data.keys())
    if missing_keys:
        raise ValidationError(f"Missing required keys: {missing_keys}")
    return True


def validate_chunk(chunk: Dict) -> bool:
    """
    Validate chunk structure.
    
    Args:
        chunk: Chunk dictionary to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If invalid
    """
    required_keys = ["document", "section", "chunk_id", "text"]
    validate_dict_keys(chunk, required_keys)
    
    if not isinstance(chunk["text"], str) or len(chunk["text"].strip()) == 0:
        raise ValidationError("Chunk text cannot be empty")
    
    return True


def validate_chunk_with_entities(chunk: Dict) -> bool:
    """
    Validate chunk with entities.
    
    Args:
        chunk: Chunk dictionary with entities
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If invalid
    """
    validate_chunk(chunk)
    
    if "entities" not in chunk:
        raise ValidationError("Chunk missing 'entities' field")
    
    required_entity_types = ["policies", "institutions", "sectors", "countries", "strategies"]
    entities = chunk["entities"]
    
    for entity_type in required_entity_types:
        if entity_type not in entities:
            raise ValidationError(f"Entities missing '{entity_type}' field")
        if not isinstance(entities[entity_type], list):
            raise ValidationError(f"Entities['{entity_type}'] must be a list")
    
    return True
