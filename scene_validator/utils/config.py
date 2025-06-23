"""Configuration utilities for SceneValidator."""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from environment variables.
    
    Args:
        config_path: Optional path to .env file
        
    Returns:
        Dictionary containing configuration values
    """
    # Load environment variables from .env file if provided
    if config_path and os.path.exists(config_path):
        load_dotenv(config_path)
    else:
        load_dotenv()  # Load from default .env file if exists
    
    # Configuration dictionary with default values
    config = {
        # API Configuration
        'API_HOST': os.environ.get('API_HOST', '0.0.0.0'),
        'API_PORT': int(os.environ.get('API_PORT', 5000)),
        'API_DEBUG': os.environ.get('API_DEBUG', 'False').lower() == 'true',
        
        # Authentication
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'default_insecure_key'),
        'JWT_EXPIRATION_HOURS': int(os.environ.get('JWT_EXPIRATION_HOURS', 24)),
        
        # Google Cloud
        'GOOGLE_APPLICATION_CREDENTIALS': os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
        'GCS_BUCKET_NAME': os.environ.get('GCS_BUCKET_NAME', 'scene-validator-media'),
        
        # Gemini API
        'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY'),
        'GEMINI_MODEL': os.environ.get('GEMINI_MODEL', 'gemini-1.5-pro-latest'),
        
        # Firestore
        'FIRESTORE_COLLECTION_VALIDATIONS': os.environ.get('FIRESTORE_COLLECTION_VALIDATIONS', 'scene_validations'),
        'FIRESTORE_COLLECTION_PROFILES': os.environ.get('FIRESTORE_COLLECTION_PROFILES', 'validation_profiles'),
        
        # Logging
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
        'LOG_FORMAT': os.environ.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
    }
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config['LOG_LEVEL']),
        format=config['LOG_FORMAT']
    )
    
    # Validate required config values
    required_keys = ['GEMINI_API_KEY']
    missing_keys = [key for key in required_keys if not config.get(key)]
    
    if missing_keys:
        logger.warning(f"Missing required configuration keys: {', '.join(missing_keys)}")
    
    return config
