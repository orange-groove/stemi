"""
RunPod API Client for stem separation
"""
import requests
import base64
import time
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RunPodClient:
    def __init__(self, api_key: str, endpoint_id: str):
        """
        Initialize RunPod client
        
        Args:
            api_key: RunPod API key
            endpoint_id: RunPod serverless endpoint ID
        """
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def encode_audio_file(self, file_path: str) -> str:
        """Encode audio file to base64"""
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def encode_audio_bytes(self, audio_bytes: bytes) -> str:
        """Encode audio bytes to base64"""
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def decode_stem(self, stem_b64: str) -> bytes:
        """Decode base64 stem back to audio bytes"""
        return base64.b64decode(stem_b64)
    
    def separate_stems_sync(self, audio_file_path: str, stems: List[str], timeout: int = 300) -> Dict:
        """
        Synchronous stem separation (blocks until complete)
        
        Args:
            audio_file_path: Path to audio file
            stems: List of stems to separate
            timeout: Maximum wait time in seconds
        
        Returns:
            Dict containing separated stems as base64 or error
        """
        try:
            # Encode audio file
            audio_b64 = self.encode_audio_file(audio_file_path)
            
            # Prepare request
            payload = {
                "input": {
                    "audio_file": audio_b64,
                    "stems": stems
                }
            }
            
            logger.info(f"Sending synchronous request to RunPod for stems: {stems}")
            
            # Send synchronous request
            response = requests.post(
                f"{self.base_url}/runsync",
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("RunPod separation completed successfully")
                return result
            else:
                logger.error(f"RunPod request failed: {response.status_code} - {response.text}")
                return {"error": f"RunPod API error: {response.status_code}"}
        
        except requests.exceptions.Timeout:
            logger.error("RunPod request timed out")
            return {"error": "Request timed out"}
        except Exception as e:
            logger.error(f"RunPod client error: {e}")
            return {"error": str(e)}
    
    def separate_stems_async(self, audio_file_path: str, stems: List[str]) -> str:
        """
        Asynchronous stem separation (returns job ID immediately)
        
        Args:
            audio_file_path: Path to audio file
            stems: List of stems to separate
        
        Returns:
            Job ID for polling status
        """
        try:
            # Encode audio file
            audio_b64 = self.encode_audio_file(audio_file_path)
            
            # Prepare request
            payload = {
                "input": {
                    "audio_file": audio_b64,
                    "stems": stems
                }
            }
            
            logger.info(f"Sending async request to RunPod for stems: {stems}")
            
            # Send async request
            response = requests.post(
                f"{self.base_url}/run",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get("id")
                logger.info(f"RunPod job submitted: {job_id}")
                return job_id
            else:
                logger.error(f"RunPod request failed: {response.status_code} - {response.text}")
                raise Exception(f"RunPod API error: {response.status_code}")
        
        except Exception as e:
            logger.error(f"RunPod client error: {e}")
            raise e
    
    def get_job_status(self, job_id: str) -> Dict:
        """
        Get status of async job
        
        Args:
            job_id: Job ID returned from async request
        
        Returns:
            Job status and results
        """
        try:
            response = requests.get(
                f"{self.base_url}/status/{job_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Status check failed: {response.status_code} - {response.text}")
                return {"error": f"Status API error: {response.status_code}"}
        
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return {"error": str(e)}
    
    def wait_for_completion(self, job_id: str, polling_interval: int = 5, max_wait: int = 300) -> Dict:
        """
        Poll job status until completion
        
        Args:
            job_id: Job ID to poll
            polling_interval: Seconds between status checks
            max_wait: Maximum wait time in seconds
        
        Returns:
            Final job result
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.get_job_status(job_id)
            
            if "error" in status:
                return status
            
            job_status = status.get("status")
            
            if job_status == "COMPLETED":
                logger.info(f"Job {job_id} completed successfully")
                return status
            elif job_status == "FAILED":
                error_msg = status.get("error", "Unknown error")
                logger.error(f"Job {job_id} failed: {error_msg}")
                return {"error": f"Job failed: {error_msg}"}
            elif job_status in ["IN_QUEUE", "IN_PROGRESS"]:
                logger.info(f"Job {job_id} status: {job_status}")
                time.sleep(polling_interval)
            else:
                logger.warning(f"Unknown job status: {job_status}")
                time.sleep(polling_interval)
        
        logger.error(f"Job {job_id} timed out after {max_wait} seconds")
        return {"error": "Job timed out"}

def create_runpod_client() -> Optional[RunPodClient]:
    """Create RunPod client from environment variables"""
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    
    if not api_key or not endpoint_id:
        logger.warning("RunPod credentials not found in environment")
        return None
    
    return RunPodClient(api_key, endpoint_id)
