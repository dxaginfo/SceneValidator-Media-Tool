"""Core SceneValidator implementation."""

import os
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

import requests
import google.generativeai as genai
from google.cloud import storage, firestore

from .utils.media import MediaProcessor
from .utils.config import load_config

logger = logging.getLogger(__name__)

class SceneValidator:
    """Main SceneValidator class for validating media scenes."""
    
    def __init__(self, api_key: Optional[str] = None, config_path: Optional[str] = None):
        """Initialize the SceneValidator.
        
        Args:
            api_key: Gemini API key (overrides environment variable)
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        
        # Initialize Gemini API
        gemini_api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("Gemini API key is required. Provide it as a parameter or set GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=gemini_api_key)
        self.model_name = self.config.get('GEMINI_MODEL', 'gemini-1.5-pro-latest')
        self.model = genai.GenerativeModel(self.model_name)
        
        # Initialize Google Cloud clients
        self.storage_client = storage.Client()
        self.db = firestore.Client()
        
        # Initialize media processor
        self.media_processor = MediaProcessor()
        
        logger.info(f"SceneValidator initialized with model {self.model_name}")
    
    def validate(self, 
                scene_id: str, 
                media_url: str, 
                validation_profile: str,
                metadata: Dict[str, Any],
                technical_requirements: Dict[str, Any],
                callback_url: Optional[str] = None) -> Dict[str, Any]:
        """Validate a media scene against specified requirements.
        
        Args:
            scene_id: Unique identifier for the scene
            media_url: URL to the media file (GCS path or HTTP URL)
            validation_profile: Name of the validation profile to use
            metadata: Scene metadata (title, description, tags, etc.)
            technical_requirements: Technical specifications for validation
            callback_url: Optional URL to call when validation completes
            
        Returns:
            Dictionary containing validation results
        """
        validation_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"Starting validation {validation_id} for scene {scene_id}")
        
        # Record the validation job
        validation_doc = {
            'validation_id': validation_id,
            'scene_id': scene_id,
            'timestamp': timestamp,
            'status': 'in_progress',
            'media_url': media_url,
            'validation_profile': validation_profile,
            'metadata': metadata,
            'technical_requirements': technical_requirements,
            'callback_url': callback_url
        }
        
        self.db.collection(self.config['FIRESTORE_COLLECTION_VALIDATIONS']).document(validation_id).set(validation_doc)
        
        try:
            # 1. Load the validation profile
            profile = self._get_validation_profile(validation_profile)
            
            # 2. Validate technical specifications
            technical_validation = self._validate_technical_specs(media_url, technical_requirements)
            
            # 3. Validate content using Gemini API
            content_validation = self._validate_content(media_url, metadata, profile)
            
            # 4. Generate recommendations
            recommendations = self._generate_recommendations(
                technical_validation['issues'] + content_validation['issues'], 
                profile
            )
            
            # 5. Compile results
            validation_passes = technical_validation['passes'] and content_validation['passes']
            status = 'passed' if validation_passes else 'failed'
            summary = self._generate_summary(technical_validation, content_validation, recommendations)
            
            # 6. Create result
            result = {
                'scene_id': scene_id,
                'validation_id': validation_id,
                'timestamp': timestamp,
                'status': status,
                'summary': summary,
                'content_validation': content_validation,
                'technical_validation': technical_validation,
                'recommendations': recommendations
            }
            
            # 7. Update validation document
            self.db.collection(self.config['FIRESTORE_COLLECTION_VALIDATIONS']).document(validation_id).update({
                'status': status,
                'result': result
            })
            
            # 8. Send callback if provided
            if callback_url:
                self._send_callback(callback_url, result)
                
            logger.info(f"Completed validation {validation_id} with status {status}")
            return result
            
        except Exception as e:
            error_message = f"Validation failed: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Update validation document with error
            self.db.collection(self.config['FIRESTORE_COLLECTION_VALIDATIONS']).document(validation_id).update({
                'status': 'error',
                'error': error_message
            })
            
            # Send error callback if provided
            if callback_url:
                self._send_callback(callback_url, {
                    'scene_id': scene_id,
                    'validation_id': validation_id,
                    'timestamp': timestamp,
                    'status': 'error',
                    'error': error_message
                })
                
            raise
    
    def _get_validation_profile(self, profile_id: str) -> Dict[str, Any]:
        """Load a validation profile from Firestore."""
        profile_doc = self.db.collection(self.config['FIRESTORE_COLLECTION_PROFILES']).document(profile_id).get()
        
        if not profile_doc.exists:
            raise ValueError(f"Validation profile '{profile_id}' not found")
            
        return profile_doc.to_dict()
    
    def _validate_technical_specs(self, media_url: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the technical specifications of the media file."""
        logger.info(f"Validating technical specifications for {media_url}")
        
        # Download media file if needed
        local_path = self.media_processor.download_media(media_url)
        
        # Extract technical metadata
        tech_metadata = self.media_processor.extract_metadata(local_path)
        
        # Compare with requirements
        issues = []
        
        # Check resolution
        if 'resolution' in requirements:
            req_width, req_height = map(int, requirements['resolution'].split('x'))
            if tech_metadata['width'] != req_width or tech_metadata['height'] != req_height:
                issues.append({
                    'type': 'resolution_mismatch',
                    'description': f"Resolution {tech_metadata['width']}x{tech_metadata['height']} does not match required {requirements['resolution']}",
                    'severity': 'high',
                    'property': 'resolution'
                })
        
        # Check framerate
        if 'framerate' in requirements:
            if abs(tech_metadata['framerate'] - requirements['framerate']) > 0.01:  # Allow small tolerance
                issues.append({
                    'type': 'framerate_mismatch',
                    'description': f"Framerate {tech_metadata['framerate']} does not match required {requirements['framerate']}",
                    'severity': 'high',
                    'property': 'framerate'
                })
        
        # Check audio channels
        if 'audio_channels' in requirements:
            if tech_metadata['audio_channels'] != requirements['audio_channels']:
                issues.append({
                    'type': 'audio_channels_mismatch',
                    'description': f"Audio channels {tech_metadata['audio_channels']} does not match required {requirements['audio_channels']}",
                    'severity': 'medium',
                    'property': 'audio_channels'
                })
        
        # Check audio sample rate
        if 'audio_sample_rate' in requirements:
            if tech_metadata['audio_sample_rate'] != requirements['audio_sample_rate']:
                issues.append({
                    'type': 'audio_sample_rate_mismatch',
                    'description': f"Audio sample rate {tech_metadata['audio_sample_rate']} does not match required {requirements['audio_sample_rate']}",
                    'severity': 'medium',
                    'property': 'audio_sample_rate'
                })
        
        # Clean up downloaded file
        self.media_processor.cleanup(local_path)
        
        return {
            'passes': len(issues) == 0,
            'issues': issues
        }
    
    def _validate_content(self, media_url: str, metadata: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content using Gemini API."""
        logger.info(f"Validating content for {media_url}")
        
        # Extract frames for analysis
        local_path = self.media_processor.download_media(media_url)
        frames = self.media_processor.extract_key_frames(local_path, 5)  # Extract 5 key frames
        
        issues = []
        
        # Prepare prompt for Gemini
        prompt = f"""
        You are a media content validator. Analyze these frames from a media scene with the following metadata:
        
        Title: {metadata.get('title', 'Unknown')}
        Description: {metadata.get('description', 'No description')}
        Tags: {', '.join(metadata.get('tags', []))}
        Intended Audience: {metadata.get('intended_audience', 'Unknown')}
        Content Rating: {metadata.get('content_rating', 'Unknown')}
        
        Validation criteria from profile '{profile.get('name', 'Unknown')}':
        {json.dumps(profile.get('content_criteria', {}), indent=2)}
        
        Identify any content issues according to these criteria. For each issue, provide:
        1. Issue type (exact match from criteria categories)
        2. Description of the specific problem
        3. Severity (low, medium, high)
        4. Frame or timecode where the issue occurs
        
        Format your response as a JSON list of issues, or an empty list if no issues found.
        """
        
        # Call Gemini API with frames
        response = self.model.generate_content(
            contents=[prompt] + [{'inline_data': {'mime_type': 'image/jpeg', 'data': frame}} for frame in frames]
        )
        
        # Parse response to extract issues
        try:
            response_text = response.text
            # Extract JSON array from response (it might be wrapped in markdown code blocks)
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_str = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_str = response_text.strip()
                
            gemini_issues = json.loads(json_str)
            issues.extend(gemini_issues)
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {str(e)}")
            issues.append({
                'type': 'validation_error',
                'description': f"Failed to analyze content: {str(e)}",
                'severity': 'high',
                'timecode': 'N/A'
            })
        
        # Clean up
        self.media_processor.cleanup(local_path)
        
        return {
            'passes': len(issues) == 0,
            'issues': issues
        }
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recommendations for identified issues."""
        if not issues:
            return []
            
        recommendations = []
        
        # Create a prompt for Gemini API to generate recommendations
        issues_json = json.dumps(issues, indent=2)
        prompt = f"""
        You are a media optimization expert. Review these issues found in a media scene validation:
        
        {issues_json}
        
        For each issue, provide a specific recommendation to fix the problem. Consider the following profile requirements:
        
        {json.dumps(profile, indent=2)}
        
        Format your response as a JSON array of recommendations, where each recommendation contains:
        1. issue_id: The index of the issue in the provided list (0, 1, 2, etc.)
        2. recommendation: A specific, actionable recommendation to fix the issue
        """
        
        try:
            response = self.model.generate_content(prompt)
            
            # Parse response to extract recommendations
            response_text = response.text
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_str = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_str = response_text.strip()
                
            recommendations = json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            recommendations = [
                {
                    'issue_id': str(i),
                    'recommendation': 'Review issue and consult technical documentation.'
                } for i in range(len(issues))
            ]
        
        return recommendations
    
    def _generate_summary(self, 
                         technical_validation: Dict[str, Any], 
                         content_validation: Dict[str, Any],
                         recommendations: List[Dict[str, Any]]) -> str:
        """Generate a human-readable summary of validation results."""
        total_issues = len(technical_validation['issues']) + len(content_validation['issues'])
        
        if total_issues == 0:
            return "Validation passed successfully. No issues found."
            
        tech_issues = len(technical_validation['issues'])
        content_issues = len(content_validation['issues'])
        
        summary = f"Validation found {total_issues} issues ({tech_issues} technical, {content_issues} content). "
        
        # Add a brief overview of the most critical issues
        high_severity_issues = [
            issue for issue in technical_validation['issues'] + content_validation['issues'] 
            if issue.get('severity') == 'high'
        ]
        
        if high_severity_issues:
            summary += f"Critical issues include: {', '.join(issue['type'] for issue in high_severity_issues[:3])}"
            if len(high_severity_issues) > 3:
                summary += f" and {len(high_severity_issues) - 3} more."
            else:
                summary += "."
        else:
            summary += "No critical issues found."
            
        return summary
    
    def _send_callback(self, callback_url: str, data: Dict[str, Any]) -> None:
        """Send validation results to the callback URL."""
        try:
            response = requests.post(
                callback_url,
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Callback sent successfully to {callback_url}")
        except Exception as e:
            logger.error(f"Failed to send callback to {callback_url}: {str(e)}")
