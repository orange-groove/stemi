"""
RunPod Serverless Handler for Stem Separation
This file will be deployed to RunPod's serverless GPU infrastructure
"""
import runpod
import torch
import torchaudio
import demucs.separate
import soundfile as sf
import numpy as np
import tempfile
import glob
import shutil
import sys
import os
import base64
import io
from pathlib import Path
import logging
# Import Supabase client for RunPod
from supabase_client import SupabaseClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize():
    """Initialize the model and GPU"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        # Clear GPU memory
        torch.cuda.empty_cache()
    else:
        device = torch.device("cpu")
        logger.info("Using CPU")
    
    return device

def separate_stems(audio_data: bytes, stems: list, device) -> dict:
    """
    Separate audio into stems using Demucs
    
    Args:
        audio_data: Raw audio file bytes
        stems: List of stems to extract
        device: Torch device
    
    Returns:
        dict: Base64 encoded stems
    """
    # Initialize result variable
    result = {"success": False, "error": "Unknown error"}
    temp_input_path = None
    temp_demucs_dir = None
    
    try:
        logger.info("=== SEPARATE_STEMS STARTED ===")
        logger.info(f"Audio data size: {len(audio_data)} bytes")
        logger.info(f"Requested stems: {stems}")
        logger.info(f"Device: {device}")
        
        # Create temporary file for input audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name
        
        logger.info(f"Created temp file: {temp_input_path}")
        
        # Load and preprocess audio
        waveform, sample_rate = torchaudio.load(temp_input_path)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample if necessary (Demucs expects 44.1kHz)
        if sample_rate != 44100:
            resampler = torchaudio.transforms.Resample(sample_rate, 44100)
            waveform = resampler(waveform)
            sample_rate = 44100
        
        # Create temporary directory for demucs output
        temp_demucs_dir = tempfile.mkdtemp()
        
        # Save original sys.argv and replace with demucs arguments
        original_argv = sys.argv.copy()
        try:
            sys.argv = [
                'demucs.separate',
                '-n', 'htdemucs_6s',
                '-d', str(device),
                '-o', temp_demucs_dir,
                temp_input_path
            ]
            
            # Run demucs separation
            logger.info("Running Demucs separation...")
            demucs.separate.main()
            logger.info("Demucs separation completed")
            
            # Find output files
            logger.info(f"Searching for output in: {temp_demucs_dir}")
            song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
            logger.info(f"Found htdemucs_6s dirs: {song_dirs}")
            
            if not song_dirs:
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
                logger.info(f"Found htdemucs dirs: {song_dirs}")
            
            if not song_dirs:
                logger.error("No Demucs output directories found")
                raise ValueError("No Demucs output found")
            
            demucs_output_dir = song_dirs[0]
            logger.info(f"Using output dir: {demucs_output_dir}")
            
            stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
            logger.info(f"Found {len(stem_files)} stem files: {[os.path.basename(f) for f in stem_files]}")
            
            # Map stem files to requested stems
            available_stems = {}
            for stem_file in stem_files:
                stem_name = Path(stem_file).stem
                if stem_name in ['vocals', 'bass', 'drums', 'other', 'guitar', 'piano']:
                    available_stems[stem_name] = stem_file
            
            # Upload requested stems to Supabase and get URLs
            logger.info("=== PROCESSING STEMS FOR SUPABASE STORAGE ===")
            
            # Debug: Check environment variables
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            logger.info(f"Environment check - SUPABASE_URL: {'SET' if supabase_url else 'NOT SET'}")
            logger.info(f"Environment check - SUPABASE_ANON_KEY: {'SET' if supabase_key else 'NOT SET'}")
            
            # Initialize Supabase client (no fallback - must work)
            try:
                supabase_client = LightweightSupabaseClient()
                logger.info("Lightweight Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Supabase client initialization failed: {e}")
                raise Exception(f"Failed to initialize Supabase client: {e}")
            
            # Prepare stem buffers for upload
            stem_buffers = {}
            for stem in stems:
                if stem in available_stems:
                    # Read the stem file
                    stem_audio, sr = torchaudio.load(available_stems[stem])
                    
                    # Convert to numpy and ensure stereo
                    stem_numpy = stem_audio.cpu().numpy()
                    if stem_numpy.shape[0] == 1:
                        stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                    
                    # Reduce sample rate to save memory (44.1kHz -> 22kHz)
                    if sr > 22050:
                        import torchaudio.transforms as T
                        resampler = T.Resample(sr, 22050)
                        stem_audio = resampler(stem_audio)
                        sr = 22050
                        stem_numpy = stem_audio.cpu().numpy()
                        if stem_numpy.shape[0] == 1:
                            stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                    
                    # Save to bytes buffer as WAV
                    buffer = io.BytesIO()
                    sf.write(buffer, stem_numpy.T, sr, format='WAV')
                    buffer.seek(0)
                    
                    # Store buffer for upload
                    stem_buffers[stem] = buffer
                    logger.info(f"Prepared {stem} stem buffer ({len(buffer.getvalue())} bytes)")
                else:
                    logger.warning(f"Requested stem '{stem}' not found in output")
            
            # Generate a unique job ID for this request
            import uuid
            job_id = str(uuid.uuid4())
            logger.info(f"Generated job ID: {job_id}")
            
            # Upload stems to Supabase (no fallback)
            try:
                # Upload stems and get URLs
                stem_urls = supabase_client.upload_stems(job_id, stem_buffers)
                logger.info(f"Successfully uploaded {len(stem_urls)} stems to Supabase")
                
                # Return Supabase URLs
                result = {
                    "success": True,
                    "job_id": job_id,
                    "stem_urls": stem_urls,
                    "available_stems": list(available_stems.keys()),
                    "storage_type": "supabase"
                }
                
            except Exception as e:
                logger.error(f"Failed to upload stems to Supabase: {e}")
                raise Exception(f"Supabase upload failed: {e}")
            
            logger.info(f"=== SEPARATION SUCCESS ===")
            logger.info(f"Job ID: {job_id}")
            logger.info(f"Storage type: supabase")
            logger.info(f"Uploaded stems: {list(result.get('stem_urls', {}).keys())}")
            logger.info(f"Stem URLs: {result.get('stem_urls', {})}")
            logger.info(f"Available stems: {result['available_stems']}")
            
            # Return success result immediately
            logger.info(f"=== RETURNING SUCCESS RESULT ===")
            return result
            
        finally:
            # Restore sys.argv
            sys.argv = original_argv
            
            # Clean up temporary files safely
            try:
                if temp_input_path and os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
            except:
                pass
            try:
                if temp_demucs_dir and os.path.exists(temp_demucs_dir):
                    shutil.rmtree(temp_demucs_dir)
            except:
                pass
            
            # Clear GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # This point should never be reached if success result was returned
        logger.error(f"=== UNEXPECTED: REACHED END WITHOUT RETURN ===")
        logger.error(f"Result type: {type(result)}")
        logger.error(f"Result success: {result.get('success', 'unknown')}")
        return {"error": "Unexpected: reached end of function without proper return"}
    
    except Exception as e:
        logger.error(f"=== SEPARATION EXCEPTION ===")
        logger.error(f"Exception: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        logger.info(f"Returning error result: {error_result}")
        return error_result

def handler(event):
    """
    RunPod serverless handler function
    
    Expected input format:
    {
        "input": {
            "audio_file": "base64_encoded_audio_data",
            "stems": ["vocals", "bass", "drums", "other"]
        }
    }
    """
    try:
        logger.info("=== HANDLER STARTED ===")
        
        # Initialize device
        logger.info("Initializing device...")
        device = initialize()
        logger.info(f"Device initialized: {device}")
        
        # Get input data
        input_data = event.get("input", {})
        logger.info(f"Input data keys: {list(input_data.keys())}")
        
        # Validate input
        if "audio_file" not in input_data:
            logger.error("Missing audio_file in input")
            return {"error": "Missing audio_file in input"}
        
        # Get stems list (default to all)
        stems = input_data.get("stems", ["vocals", "bass", "drums", "other"])
        logger.info(f"Requested stems: {stems}")
        
        # Decode base64 audio data
        try:
            audio_b64 = input_data["audio_file"]
            logger.info(f"Audio data length: {len(audio_b64)} characters")
            audio_data = base64.b64decode(audio_b64)
            logger.info(f"Decoded audio size: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Failed to decode audio data: {e}")
            return {"error": f"Failed to decode audio data: {str(e)}"}
        
        logger.info(f"Starting stem separation for stems: {stems}")
        
        # Perform stem separation
        result = separate_stems(audio_data, stems, device)
        logger.info(f"Separation result keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")
        
        if result["success"]:
            logger.info("=== HANDLER SUCCESS ===")
            response = {
                "status": "completed",
                "stem_urls": result["stem_urls"],
                "available_stems": result["available_stems"],
                "storage_type": result["storage_type"]
            }
            logger.info(f"Final response stem URLs count: {len(result['stem_urls'])}")
            logger.info(f"Final response keys: {list(response.keys())}")
            logger.info("=== HANDLER RETURNING SUCCESS ===")
            return response
        else:
            logger.error(f"=== HANDLER FAILURE ===")
            logger.error(f"Separation failed: {result['error']}")
            error_response = {"error": result["error"]}
            logger.info(f"Returning error response: {error_response}")
            logger.info("=== HANDLER RETURNING ERROR ===")
            return error_response
    
    except Exception as e:
        logger.error(f"=== HANDLER EXCEPTION ===")
        logger.error(f"Handler error: {e}")
        import traceback
        logger.error(f"Handler traceback: {traceback.format_exc()}")
        final_error = {"error": f"Handler error: {str(e)}"}
        logger.info(f"Returning final error: {final_error}")
        logger.info("=== HANDLER RETURNING EXCEPTION ===")
        return final_error

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
