# SceneValidator

Media scene validation tool using Gemini API and Google Cloud.

## Overview

SceneValidator is an automated tool for validating media scenes against industry standards, content requirements, and technical specifications. It leverages Gemini API for content analysis and Google Cloud services for processing and storage.

## Features

- Automated scene validation against predefined criteria
- Content analysis using Gemini API
- Technical validation of media properties
- Integration with media workflow systems
- Batch processing capabilities
- Comprehensive reporting

## Installation

```bash
# Clone the repository
git clone https://github.com/dxaginfo/SceneValidator-Media-Tool.git
cd SceneValidator-Media-Tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### REST API

Start the API server:

```bash
python -m scene_validator.api.server
```

Send a validation request:

```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "scene_id": "scene123",
    "media_url": "gs://your-bucket/your-media.mp4",
    "validation_profile": "broadcast_standards",
    "metadata": {
      "title": "Example Scene",
      "description": "A sample scene for validation",
      "tags": ["drama", "indoor", "dialogue"],
      "intended_audience": "general",
      "content_rating": "PG"
    },
    "technical_requirements": {
      "resolution": "1920x1080",
      "framerate": 29.97,
      "color_space": "rec709",
      "audio_channels": 2,
      "audio_sample_rate": 48000
    }
  }'
```

### Python Client

```python
from scene_validator import SceneValidator

validator = SceneValidator(api_key="your_api_key")

result = validator.validate(
    scene_id="scene123",
    media_url="gs://your-bucket/your-media.mp4",
    validation_profile="broadcast_standards",
    metadata={
        "title": "Example Scene",
        "description": "A sample scene for validation",
        "tags": ["drama", "indoor", "dialogue"],
        "intended_audience": "general",
        "content_rating": "PG"
    },
    technical_requirements={
        "resolution": "1920x1080",
        "framerate": 29.97,
        "color_space": "rec709",
        "audio_channels": 2,
        "audio_sample_rate": 48000
    }
)

print(f"Validation status: {result['status']}")
print(f"Summary: {result['summary']}")
```

## Documentation

For full documentation, see the [official documentation](https://docs.google.com/document/d/1Tzd-zwtC4g5cXFVy-DMB0ZlwHNHwLKeJvvH86EjcVD4/edit).

## License

MIT
