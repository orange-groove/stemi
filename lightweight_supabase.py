"""
Lightweight Supabase client using only requests
Specifically designed for RunPod environment to avoid heavy dependencies
"""
import os
import requests
import logging
from typing import Dict, BinaryIO

logger = logging.getLogger(__name__)

class LightweightSupabaseClient:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.bucket_name = "stems"
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
        
        # Build storage API URL
        self.storage_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}"
        
        # Headers for requests
        self.headers = {
            "Authorization": f"Bearer {self.supabase_key}",
            "apikey": self.supabase_key,
        }
        
        logger.info("Lightweight Supabase client initialized")

    def upload_file(self, file_path: str, file_data: bytes, content_type: str = "audio/wav") -> str:
        """
        Upload a file to Supabase storage and return public URL
        
        Args:
            file_path: Storage path (e.g., "stems/job_id/vocals.wav")
            file_data: Binary file data
            content_type: MIME type
            
        Returns:
            Public URL of uploaded file
        """
        try:
            # Upload file
            upload_headers = self.headers.copy()
            upload_headers["Content-Type"] = content_type
            
            response = requests.post(
                self.storage_url + "/" + file_path,
                headers=upload_headers,
                data=file_data,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                # Return public URL
                public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{file_path}"
                logger.info(f"Successfully uploaded to: {public_url}")
                return public_url
            else:
                logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                raise Exception(f"Upload failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            raise

    def upload_stems(self, job_id: str, stem_buffers: Dict[str, BinaryIO]) -> Dict[str, str]:
        """
        Upload multiple stems and return their URLs
        
        Args:
            job_id: Unique job identifier
            stem_buffers: Dict of stem_name -> BytesIO buffer
            
        Returns:
            Dict of stem_name -> public_url
        """
        uploaded_urls = {}
        
        for stem_name, buffer in stem_buffers.items():
            file_path = f"stems/{job_id}/{stem_name}.wav"
            file_data = buffer.getvalue()
            
            try:
                public_url = self.upload_file(file_path, file_data, "audio/wav")
                uploaded_urls[stem_name] = public_url
                logger.info(f"Uploaded {stem_name}: {public_url}")
            except Exception as e:
                logger.error(f"Failed to upload {stem_name}: {e}")
                raise
        
        return uploaded_urls
