from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import asyncio
from pathlib import Path
from typing import List, Optional
import logging
from enum import Enum
from datetime import datetime
from runpod_client import create_runpod_client, RunPodClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Job status tracking (simplified for RunPod)
class JobStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_QUEUE = "in_queue"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class RunPodJob:
    def __init__(self, job_id: str, runpod_job_id: str, stems: list):
        self.job_id = job_id
        self.runpod_job_id = runpod_job_id
        self.stems = stems
        self.status = JobStatus.SUBMITTED
        self.created_at = datetime.now()
        self.completed_at = None
        self.result = None
        self.error = None

# Job tracking
active_jobs = {}  # job_id -> RunPodJob

app = FastAPI(
    title="STEMI Separation Service",
    description="GPU-accelerated stem separation using Demucs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
runpod_client = None

# Initialize directories (support both local and Docker environments)
UPLOAD_DIR = Path("uploads") if not Path("/app").exists() else Path("/app/uploads")
OUTPUT_DIR = Path("outputs") if not Path("/app").exists() else Path("/app/outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

async def sync_runpod_jobs():
    """Background task to sync RunPod job statuses"""
    while True:
        try:
            if not runpod_client:
                await asyncio.sleep(10)
                continue
            
            # Check status of all pending jobs
            pending_jobs = [job for job in active_jobs.values() 
                          if job.status in [JobStatus.SUBMITTED, JobStatus.IN_QUEUE, JobStatus.IN_PROGRESS]]
            
            for job in pending_jobs:
                try:
                    status_response = runpod_client.get_job_status(job.runpod_job_id)
                    
                    if "error" in status_response:
                        job.status = JobStatus.FAILED
                        job.error = status_response["error"]
                        job.completed_at = datetime.now()
                        continue
                    
                    runpod_status = status_response.get("status")
                    
                    # Map RunPod status to our status
                    if runpod_status == "IN_QUEUE":
                        job.status = JobStatus.IN_QUEUE
                    elif runpod_status == "IN_PROGRESS":
                        job.status = JobStatus.IN_PROGRESS
                    elif runpod_status == "COMPLETED":
                        job.status = JobStatus.COMPLETED
                        job.completed_at = datetime.now()
                        job.result = status_response.get("output", {})
                    elif runpod_status == "FAILED":
                        job.status = JobStatus.FAILED
                        job.error = status_response.get("error", "Unknown error")
                        job.completed_at = datetime.now()
                    
                except Exception as e:
                    logger.error(f"Error checking status for job {job.job_id}: {e}")
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in RunPod sync: {e}")
            await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    """Initialize RunPod client and background tasks"""
    global runpod_client
    
    try:
        # Initialize RunPod client
        runpod_client = create_runpod_client()
        if runpod_client:
            logger.info("RunPod client initialized successfully")
        else:
            logger.warning("RunPod credentials not found - separation will not work")
        
        # Start background job status sync
        asyncio.create_task(sync_runpod_jobs())
        logger.info("Background RunPod sync started")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise e

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "STEMI Separation Service",
        "status": "running",
        "runpod_available": runpod_client is not None
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "runpod_available": runpod_client is not None,
        "active_jobs": len(active_jobs)
    }

@app.post("/separate")
async def separate_audio(
    file: UploadFile = File(...),
    stems: Optional[str] = None
):
    """
    Upload an audio file and submit it to RunPod for stem separation
    """
    try:
        if not runpod_client:
            raise HTTPException(status_code=503, detail="RunPod service not available")
        
        # Validate file type
        if not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Parse stems parameter
        stem_list = ["vocals", "bass", "drums", "other"]  # default
        if stems:
            stem_list = [s.strip() for s in stems.split(",")]
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Read file content
        content = await file.read()
        
        logger.info(f"Submitting job {job_id} to RunPod for stems: {stem_list}")
        
        # Save file temporarily for RunPod submission
        file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # Submit to RunPod
        try:
            runpod_job_id = runpod_client.separate_stems_async(str(file_path), stem_list)
            
            # Create job tracking
            job = RunPodJob(job_id, runpod_job_id, stem_list)
            active_jobs[job_id] = job
            
            logger.info(f"Job {job_id} submitted to RunPod as {runpod_job_id}")
            
            # Clean up local file after submission
            os.remove(file_path)
            
            return {
                "job_id": job_id,
                "status": "submitted",
                "message": "Job submitted to RunPod for processing",
                "runpod_job_id": runpod_job_id
            }
            
        except Exception as e:
            # Clean up file on error
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"Failed to submit to RunPod: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in separate_audio: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/download/{job_id}/{stem}")
async def download_stem(job_id: str, stem: str):
    """
    Download a specific stem from a completed RunPod job
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = active_jobs[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    if not job.result or "stems" not in job.result:
        raise HTTPException(status_code=404, detail="No stems available for this job")
    
    if stem not in job.result["stems"]:
        available_stems = list(job.result["stems"].keys())
        raise HTTPException(
            status_code=404, 
            detail=f"Stem '{stem}' not found. Available stems: {available_stems}"
        )
    
    # Decode base64 stem data
    import base64
    import io
    from fastapi.responses import StreamingResponse
    
    try:
        stem_b64 = job.result["stems"][stem]
        stem_bytes = base64.b64decode(stem_b64)
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(stem_bytes),
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename={stem}.wav"}
        )
    except Exception as e:
        logger.error(f"Error downloading stem {stem} for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error processing stem file")

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status and results for a RunPod job
    """
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = active_jobs[job_id]
    
    response = {
        "job_id": job_id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "runpod_job_id": job.runpod_job_id,
        "stems": job.stems
    }
    
    if job.status == JobStatus.SUBMITTED:
        response.update({
            "message": "Job submitted to RunPod, waiting for processing to start"
        })
    elif job.status == JobStatus.IN_QUEUE:
        response.update({
            "message": "Job is queued in RunPod, waiting for available GPU"
        })
    elif job.status == JobStatus.IN_PROGRESS:
        response.update({
            "message": "Job is currently being processed on RunPod GPU"
        })
    elif job.status == JobStatus.COMPLETED:
        if job.result:
            # Convert base64 stems to download URLs
            stems_available = []
            if "stems" in job.result:
                stems_available = list(job.result["stems"].keys())
            
            response.update({
                "message": "Job completed successfully",
                "stems_available": stems_available,
                "download_info": "Use /download/{job_id}/{stem} to download individual stems"
            })
        else:
            response["message"] = "Job completed but no result available"
    elif job.status == JobStatus.FAILED:
        response.update({
            "message": "Job failed",
            "error": job.error
        })
    
    return response

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a job and its output files
    """
    job_dir = OUTPUT_DIR / job_id
    
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove all files in the job directory
    for file in job_dir.glob("*"):
        file.unlink()
    
    # Remove the directory
    job_dir.rmdir()
    
    # Clean up Supabase storage
    if supabase_storage:
        try:
            supabase_storage.delete_stems(job_id)
            logger.info(f"Deleted Supabase stems for job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to delete Supabase stems: {e}")
    
    return {"message": f"Job {job_id} deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
