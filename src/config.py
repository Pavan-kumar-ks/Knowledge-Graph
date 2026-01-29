"""
Configuration management for the Policy Knowledge Graph pipeline.
Supports environment-based configuration with fallbacks.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Base configuration class with all necessary settings."""

    # Static paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    PDF_DIR = DATA_DIR / "pdfs"
    OUTPUT_DIR = BASE_DIR / "output"
    LOGS_DIR = BASE_DIR / "logs"
    CHUNKS_FILE = OUTPUT_DIR / "chunks.json"
    CHUNKS_ENTITIES_FILE = OUTPUT_DIR / "chunks_with_entities.json"
    LOG_FILE = LOGS_DIR / "pipeline.log"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __init__(self):
        # Neo4j Configuration
        self.NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        self.NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "chandan01245")
        self.NEO4J_TIMEOUT = int(os.getenv("NEO4J_TIMEOUT", "30"))

        # Chunking Configuration
        self.CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))
        self.CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))

        # Groq API Configuration
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        self.GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.1"))
        self.GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "2000"))
        self.GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "3"))
        self.GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "60"))

        # Logging Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.DEBUG = os.getenv("DEBUG", "False").lower() == "true"

        # Pipeline Configuration
        self.BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        if not cls.PDF_DIR.exists():
            raise ValueError(f"PDF directory not found: {cls.PDF_DIR}")
        
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        return True


class DevelopmentConfig(Config):
    """Development environment configuration."""
    def __init__(self):
        super().__init__()
        self.DEBUG = True
        self.LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Production environment configuration."""
    def __init__(self):
        super().__init__()
        self.DEBUG = False
        self.LOG_LEVEL = "WARNING"
        self.NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://your-aura-instance.neo4jdb.com")


class TestConfig(Config):
    """Test environment configuration."""
    def __init__(self):
        super().__init__()
        self.DEBUG = True
        self.LOG_LEVEL = "DEBUG"
        self.NEO4J_URI = "neo4j://127.0.0.1:7687"


def get_config() -> Config:
    """
    Get configuration based on environment.
    
    Environment variable: CONFIG_ENV (development, production, test)
    Default: development
    """
    env = os.getenv("CONFIG_ENV", "development").lower()
    
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "test": TestConfig
    }
    
    config_class = config_map.get(env, DevelopmentConfig)
    return config_class()


# Default config instance
config = get_config()
