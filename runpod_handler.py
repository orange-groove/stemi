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
    try:
        # Create temporary file for input audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name
        
        logger.info(f"Processing audio file: {temp_input_path}")
        
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
            
            # Find output files
            song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
            if not song_dirs:
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
            
            if not song_dirs:
                raise ValueError("No Demucs output found")
            
            demucs_output_dir = song_dirs[0]
            stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
            
            logger.info(f"Found {len(stem_files)} stem files")
            
            # Map stem files to requested stems
            available_stems = {}
            for stem_file in stem_files:
                stem_name = Path(stem_file).stem
                if stem_name in ['vocals', 'bass', 'drums', 'other', 'guitar', 'piano']:
                    available_stems[stem_name] = stem_file
            
            # Encode requested stems as base64
            result_stems = {}
            for stem in stems:
                if stem in available_stems:
                    # Read the stem file
                    stem_audio, sr = torchaudio.load(available_stems[stem])
                    
                    # Convert to numpy and ensure stereo
                    stem_numpy = stem_audio.cpu().numpy()
                    if stem_numpy.shape[0] == 1:
                        stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                    
                    # Save to bytes buffer as WAV
                    buffer = io.BytesIO()
                    sf.write(buffer, stem_numpy.T, sr, format='WAV')
                    buffer.seek(0)
                    
                    # Encode as base64
                    stem_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    result_stems[stem] = stem_b64
                    
                    logger.info(f"Encoded {stem} stem")
                else:
                    logger.warning(f"Requested stem '{stem}' not found in output")
            
            result = {
                "success": True,
                "stems": result_stems,
                "available_stems": list(available_stems.keys())
            }
            
        finally:
            # Restore sys.argv
            sys.argv = original_argv
            
            # Clean up temporary files safely
            try:
                if os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
            except:
                pass
            try:
                if os.path.exists(temp_demucs_dir):
                    shutil.rmtree(temp_demucs_dir)
            except:
                pass
            
            # Clear GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return result
    
    except Exception as e:
        logger.error(f"Error during stem separation: {e}")
        return {
            "success": False,
            "error": str(e)
        }

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
        # Initialize device
        device = initialize()
        
        # Get input data
        input_data = event.get("input", {})
        
        # Validate input
        if "audio_file" not in input_data:
            return {"error": "Missing audio_file in input"}
        
        # Get stems list (default to all)
        stems = input_data.get("stems", ["vocals", "bass", "drums", "other"])
        
        # Decode base64 audio data
        try:
            audio_b64 = input_data["audio_file"]
            audio_data = base64.b64decode(audio_b64)
        except Exception as e:
            return {"error": f"Failed to decode audio data: {str(e)}"}
        
        logger.info(f"Processing separation request for stems: {stems}")
        
        # Perform stem separation
        result = separate_stems(audio_data, stems, device)
        
        if result["success"]:
            logger.info("Separation completed successfully")
            return {
                "status": "completed",
                "stems": result["stems"],
                "available_stems": result["available_stems"]
            }
        else:
            logger.error(f"Separation failed: {result['error']}")
            return {"error": result["error"]}
    
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
