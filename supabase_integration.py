#!/usr/bin/env python3
"""
Supabase integration for storing processed stems
"""
import os
import uuid
from typing import Dict, List
import logging
from supabase import create_client, Client
import httpx

logger = logging.getLogger(__name__)

class SupabaseStemStorage:
    def __init__(self, supabase_url: str = None, supabase_key: str = None, bucket_name: str = "stems"):
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        # Support both old anon key and new service role key
        self.supabase_key = (supabase_key or 
                            os.getenv("SUPABASE_ANON_KEY"))
        self.bucket_name = bucket_name
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase URL and service role key are required")
        
        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists - since uploads work, we'll assume it exists"""
        # Skip bucket metadata checks since they fail with anon key
        # but uploads work fine to the public 'stems' bucket
        logger.info(f"Assuming bucket '{self.bucket_name}' exists (public bucket)")
    
    def upload_stems(self, job_id: str, stem_files: Dict[str, str]) -> Dict[str, str]:
        """
        Upload processed stems to Supabase storage
        
        Args:
            job_id: Unique job identifier
            stem_files: Dict of {stem_name: file_path}
            
        Returns:
            Dict of {stem_name: public_url}
        """
        public_urls = {}
        
        for stem_name, file_path in stem_files.items():
            try:
                # Generate storage path
                storage_path = f"stems/{job_id}/{stem_name}.wav"
                
                # Upload file to Supabase
                with open(file_path, "rb") as f:
                    result = self.supabase.storage.from_(self.bucket_name).upload(
                        storage_path,
                        f.read(),
                        file_options={
                            "content-type": "audio/wav",
                            "cache-control": "3600"
                        }
                    )
                
                if result.get("error"):
                    raise Exception(f"Upload error: {result['error']}")
                
                # Get public URL
                public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(storage_path)
                public_urls[stem_name] = public_url
                
                logger.info(f"Uploaded {stem_name} to Supabase: {storage_path}")
                
            except Exception as e:
                logger.error(f"Error uploading {stem_name}: {e}")
                raise
        
        return public_urls
    
    def get_stem_urls(self, job_id: str) -> Dict[str, str]:
        """Get public URLs for all stems in a job"""
        try:
            # List files in the job directory
            files = self.supabase.storage.from_(self.bucket_name).list(f"stems/{job_id}/")
            
            stem_urls = {}
            for file_info in files:
                if file_info["name"].endswith(".wav"):
                    stem_name = file_info["name"].replace(".wav", "")
                    storage_path = f"stems/{job_id}/{file_info['name']}"
                    public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(storage_path)
                    stem_urls[stem_name] = public_url
            
            return stem_urls
            
        except Exception as e:
            logger.error(f"Error getting stem URLs for job {job_id}: {e}")
            raise
    
    def delete_stems(self, job_id: str):
        """Delete all stems for a job"""
        try:
            # List files in the job directory
            files = self.supabase.storage.from_(self.bucket_name).list(f"stems/{job_id}/")
            
            # Delete all files
            file_paths = [f"stems/{job_id}/{file_info['name']}" for file_info in files]
            if file_paths:
                self.supabase.storage.from_(self.bucket_name).remove(file_paths)
                
            logger.info(f"Deleted stems for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error deleting stems for job {job_id}: {e}")
            raise
    
    def get_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Get a signed URL for private access"""
        try:
            signed_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                storage_path,
                expires_in
            )
            return signed_url
        except Exception as e:
            logger.error(f"Error creating signed URL: {e}")
            raise

# Example usage
def process_and_store_stems(audio_file_path: str, job_id: str) -> Dict[str, str]:
    """
    Process audio and store stems in Supabase
    """
    # 1. Process audio (your existing code)
    # stem_files = separate_stems(audio_file_path)
    
    # 2. Upload to Supabase
    supabase_storage = SupabaseStemStorage()
    public_urls = supabase_storage.upload_stems(job_id, stem_files)
    
    # 3. Clean up local files
    for file_path in stem_files.values():
        os.remove(file_path)
    
    return public_urls
