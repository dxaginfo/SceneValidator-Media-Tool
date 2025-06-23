"""Flask REST API server for SceneValidator."""

import os
import json
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional

from flask import Flask, request, jsonify, g
import jwt

from ..validator import SceneValidator
from ..utils.config import load_config

# Configure logging
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config['SECRET_KEY']

# Initialize SceneValidator
validator = SceneValidator()

# Authentication decorator
def token_required(f: Callable) -> Callable:
    """Decorator to require JWT token for API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
            
        try:
            # Decode token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            g.user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
            
        return f(*args, **kwargs)
    
    return decorated

# API Routes
@app.route('/health', methods=['GET'])
def health_check() -> tuple:
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'version': '0.1.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200

@app.route('/validate', methods=['POST'])
@token_required
def validate_scene() -> tuple:
    """Endpoint to validate a media scene."""
    data = request.json
    
    # Validate request data
    required_fields = ['scene_id', 'media_url', 'validation_profile', 'metadata', 'technical_requirements']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({
            'error': f"Missing required fields: {', '.join(missing_fields)}"
        }), 400
    
    try:
        # Call validator
        result = validator.validate(
            scene_id=data['scene_id'],
            media_url=data['media_url'],
            validation_profile=data['validation_profile'],
            metadata=data['metadata'],
            technical_requirements=data['technical_requirements'],
            callback_url=data.get('callback_url')
        )
        
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception(f"Error during validation: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/validation/<validation_id>', methods=['GET'])
@token_required
def get_validation_result(validation_id: str) -> tuple:
    """Endpoint to retrieve validation results."""
    try:
        # Get validation from Firestore
        validation_doc = validator.db.collection(config['FIRESTORE_COLLECTION_VALIDATIONS']).document(validation_id).get()
        
        if not validation_doc.exists:
            return jsonify({'error': f"Validation with ID {validation_id} not found"}), 404
            
        return jsonify(validation_doc.to_dict()), 200
    except Exception as e:
        logger.exception(f"Error retrieving validation {validation_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/profiles', methods=['GET'])
@token_required
def list_validation_profiles() -> tuple:
    """Endpoint to list available validation profiles."""
    try:
        # Get profiles from Firestore
        profiles = []
        for doc in validator.db.collection(config['FIRESTORE_COLLECTION_PROFILES']).stream():
            profile_data = doc.to_dict()
            profiles.append({
                'id': doc.id,
                'name': profile_data.get('name', 'Unnamed Profile'),
                'description': profile_data.get('description', '')
            })
            
        return jsonify({'profiles': profiles}), 200
    except Exception as e:
        logger.exception(f"Error listing validation profiles: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Main entry point
if __name__ == '__main__':
    app.run(
        host=config['API_HOST'],
        port=config['API_PORT'],
        debug=config['API_DEBUG']
    )
