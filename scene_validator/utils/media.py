"""Media processing utilities for SceneValidator."""

import os
import uuid
import tempfile
import logging
from typing import Dict, List, Any, Optional, Union

import ffmpeg
import numpy as np
import cv2
from google.cloud import storage

logger = logging.getLogger(__name__)

class MediaProcessor:
    """Class for processing media files."""
    
    def __init__(self):
        """Initialize the MediaProcessor."""
        self.storage_client = storage.Client()
        self.temp_dir = tempfile.gettempdir()
    
    def download_media(self, media_url: str) -> str:
        """Download media file from URL or GCS path.
        
        Args:
            media_url: URL or GCS path to media file
            
        Returns:
            Local path to downloaded file
        """
        logger.info(f"Downloading media from {media_url}")
        
        local_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.mp4")
        
        if media_url.startswith('gs://'):
            # Parse GCS path
            bucket_name = media_url.split('/')[2]
            blob_path = '/'.join(media_url.split('/')[3:])
            
            # Download from GCS
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.download_to_filename(local_path)
        else:
            # Assume HTTP URL - use ffmpeg to download
            try:
                (ffmpeg
                    .input(media_url)
                    .output(local_path, c='copy')
                    .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
                )
            except ffmpeg.Error as e:
                logger.error(f"Failed to download media from {media_url}: {e.stderr.decode()}")
                raise
        
        logger.info(f"Media downloaded to {local_path}")
        return local_path
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract technical metadata from media file.
        
        Args:
            file_path: Path to local media file
            
        Returns:
            Dictionary of technical metadata
        """
        logger.info(f"Extracting metadata from {file_path}")
        
        try:
            # Use ffprobe to get metadata
            probe = ffmpeg.probe(file_path)
            
            # Extract video stream data
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found in file")
                
            # Extract audio stream data
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            
            # Parse frame rate
            framerate = 0
            if 'avg_frame_rate' in video_stream:
                num, den = map(int, video_stream['avg_frame_rate'].split('/'))
                if den != 0:  # Avoid division by zero
                    framerate = num / den
            
            # Build metadata dictionary
            metadata = {
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'duration': float(probe.get('format', {}).get('duration', 0)),
                'size': int(probe.get('format', {}).get('size', 0)),
                'framerate': framerate,
                'codec': video_stream.get('codec_name', 'unknown'),
                'audio_channels': int(audio_stream.get('channels', 0)) if audio_stream else 0,
                'audio_sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
                'audio_codec': audio_stream.get('codec_name', 'none') if audio_stream else 'none',
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata from {file_path}: {str(e)}")
            raise
    
    def extract_key_frames(self, file_path: str, num_frames: int = 5) -> List[bytes]:
        """Extract key frames from video for content analysis.
        
        Args:
            file_path: Path to local video file
            num_frames: Number of frames to extract
            
        Returns:
            List of frame images as bytes
        """
        logger.info(f"Extracting {num_frames} key frames from {file_path}")
        
        # Get video metadata
        metadata = self.extract_metadata(file_path)
        duration = metadata['duration']
        
        # Calculate timestamps for evenly distributed frames
        timestamps = [duration * i / (num_frames - 1) if num_frames > 1 else duration / 2 for i in range(num_frames)]
        
        # Extract frames using OpenCV
        frames = []
        cap = cv2.VideoCapture(file_path)
        
        for ts in timestamps:
            # Set position to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            
            # Read frame
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Failed to read frame at timestamp {ts}s")
                continue
                
            # Convert to JPEG bytes
            _, buffer = cv2.imencode('.jpg', frame)
            frames.append(buffer.tobytes())
        
        cap.release()
        logger.info(f"Extracted {len(frames)} frames from {file_path}")
        
        return frames
    
    def cleanup(self, file_path: str) -> None:
        """Clean up temporary files.
        
        Args:
            file_path: Path to file to delete
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temporary file {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {str(e)}")
