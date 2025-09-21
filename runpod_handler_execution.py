#!/usr/bin/env python3
"""
Test actual Demucs execution on RunPod to find where it fails
"""

import runpod
import logging
import base64
import tempfile
import os
import sys
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event):
    """
    Test actual Demucs execution step by step
    """
    try:
        logger.info("=== TESTING DEMUCS EXECUTION ===")
        
        # Import everything we need
        import torch
        import torchaudio
        import demucs.separate
        import glob
        from pathlib import Path
        
        input_data = event.get("input", {})
        
        # Validate we have audio data
        if "audio_file" not in input_data:
            return {"error": "Missing audio_file in input"}
        
        # Decode audio
        audio_b64 = input_data["audio_file"]
        audio_data = base64.b64decode(audio_b64)
        
        logger.info(f"Audio data size: {len(audio_data)} bytes")
        
        # Setup device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")
        
        # Create temp files
        temp_input_path = None
        temp_demucs_dir = None
        
        try:
            # Create temp input file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input_path = temp_input.name
            
            logger.info(f"Created temp input: {temp_input_path}")
            
            # Create temp output directory
            temp_demucs_dir = tempfile.mkdtemp()
            logger.info(f"Created temp output dir: {temp_demucs_dir}")
            
            # Test: Try to load the audio file first
            try:
                waveform, sample_rate = torchaudio.load(temp_input_path)
                logger.info(f"Audio loaded successfully: {waveform.shape}, SR: {sample_rate}")
            except Exception as e:
                return {"error": f"Audio loading failed: {e}", "step": "audio_loading"}
            
            # Test: Setup sys.argv for Demucs
            original_argv = sys.argv.copy()
            
            sys.argv = [
                'demucs.separate',
                '-n', 'htdemucs_6s',
                '-d', str(device),
                '-o', temp_demucs_dir,
                temp_input_path
            ]
            
            logger.info(f"Demucs args: {sys.argv}")
            
            # Test: Run Demucs with timeout simulation
            try:
                logger.info("🎵 Starting Demucs separation...")
                
                # This is where it likely fails
                demucs.separate.main()
                
                logger.info("✅ Demucs completed successfully!")
                
                # Restore argv
                sys.argv = original_argv
                
                # Check output
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
                if not song_dirs:
                    song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
                
                if song_dirs:
                    demucs_output_dir = song_dirs[0]
                    stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
                    
                    return {
                        "success": True,
                        "message": "Demucs execution successful!",
                        "stems_found": len(stem_files),
                        "stem_names": [Path(f).stem for f in stem_files],
                        "output_dir": demucs_output_dir
                    }
                else:
                    # List all files for debugging
                    all_files = []
                    for root, dirs, files in os.walk(temp_demucs_dir):
                        for file in files:
                            all_files.append(os.path.join(root, file))
                    
                    return {
                        "error": "No Demucs output found",
                        "step": "output_search",
                        "all_files": all_files,
                        "temp_dir": temp_demucs_dir
                    }
                
            except Exception as e:
                # Restore argv on error
                sys.argv = original_argv
                return {
                    "error": f"Demucs execution failed: {e}",
                    "step": "demucs_execution",
                    "error_type": type(e).__name__
                }
        
        finally:
            # Cleanup
            try:
                if temp_input_path and os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
                if temp_demucs_dir and os.path.exists(temp_demucs_dir):
                    shutil.rmtree(temp_demucs_dir)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
        
    except Exception as e:
        import traceback
        return {
            "error": f"Handler error: {e}",
            "traceback": traceback.format_exc(),
            "step": "top_level"
        }

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
