#!/usr/bin/env python3
"""
Test the complete process: Demucs execution + stem encoding
Now we know Demucs works, let's test the encoding step
"""

import runpod
import logging
import base64
import tempfile
import os
import sys
import shutil
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event):
    """
    Test complete process: Demucs + encoding
    """
    try:
        logger.info("=== TESTING FULL DEMUCS + ENCODING ===")
        
        # Import everything
        import torch
        import torchaudio
        import demucs.separate
        import glob
        import soundfile as sf
        import numpy as np
        from pathlib import Path
        
        input_data = event.get("input", {})
        
        if "audio_file" not in input_data:
            return {"error": "Missing audio_file in input"}
        
        # Decode audio
        audio_b64 = input_data["audio_file"]
        audio_data = base64.b64decode(audio_b64)
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        stems_requested = input_data.get("stems", ["vocals", "bass", "drums", "other"])
        
        temp_input_path = None
        temp_demucs_dir = None
        
        try:
            # Create temp files
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input_path = temp_input.name
            
            temp_demucs_dir = tempfile.mkdtemp()
            
            # Run Demucs
            original_argv = sys.argv.copy()
            sys.argv = [
                'demucs.separate',
                '-n', 'htdemucs_6s', 
                '-d', str(device),
                '-o', temp_demucs_dir,
                temp_input_path
            ]
            
            logger.info("🎵 Running Demucs...")
            demucs.separate.main()
            logger.info("✅ Demucs completed")
            
            sys.argv = original_argv
            
            # Find output files
            song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
            if not song_dirs:
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
            
            if not song_dirs:
                return {"error": "No Demucs output found"}
            
            demucs_output_dir = song_dirs[0]
            stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
            
            logger.info(f"Found {len(stem_files)} stem files")
            
            # Map stem files
            available_stems = {}
            for stem_file in stem_files:
                stem_name = Path(stem_file).stem
                available_stems[stem_name] = stem_file
            
            logger.info(f"Available stems: {list(available_stems.keys())}")
            
            # NOW TEST THE ENCODING STEP (this might be where it fails)
            result_stems = {}
            
            for stem in stems_requested:
                if stem in available_stems:
                    try:
                        logger.info(f"🎯 Encoding {stem} stem...")
                        
                        # Load audio
                        stem_audio, sr = torchaudio.load(available_stems[stem])
                        logger.info(f"✅ Loaded {stem}: {stem_audio.shape}, SR: {sr}")
                        
                        # Convert to numpy
                        stem_numpy = stem_audio.cpu().numpy()
                        if stem_numpy.shape[0] == 1:
                            stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                        
                        logger.info(f"✅ Converted {stem} to numpy: {stem_numpy.shape}")
                        
                        # Encode to WAV bytes
                        buffer = io.BytesIO()
                        sf.write(buffer, stem_numpy.T, sr, format='WAV')
                        buffer.seek(0)
                        
                        wav_bytes = buffer.getvalue()
                        logger.info(f"✅ WAV bytes for {stem}: {len(wav_bytes)} bytes")
                        
                        # Encode to base64 (this might cause memory issues?)
                        stem_b64 = base64.b64encode(wav_bytes).decode('utf-8')
                        logger.info(f"✅ Base64 for {stem}: {len(stem_b64)} chars")
                        
                        result_stems[stem] = stem_b64
                        
                        logger.info(f"✅ Successfully encoded {stem} stem")
                        
                    except Exception as e:
                        return {
                            "error": f"Failed to encode {stem}: {e}",
                            "step": f"encoding_{stem}",
                            "stems_processed_so_far": list(result_stems.keys())
                        }
            
            # Test creating final response (this might fail too)
            try:
                logger.info("🎯 Creating final response...")
                
                response = {
                    "status": "completed",
                    "stems": result_stems,
                    "available_stems": list(available_stems.keys()),
                    "stems_count": len(result_stems),
                    "device_used": str(device)
                }
                
                logger.info(f"✅ Response created with {len(result_stems)} stems")
                logger.info(f"✅ Response keys: {list(response.keys())}")
                
                return response
                
            except Exception as e:
                return {
                    "error": f"Failed to create response: {e}",
                    "step": "response_creation",
                    "stems_encoded": len(result_stems)
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
                logger.info("✅ Cleanup completed")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
    
    except Exception as e:
        import traceback
        return {
            "error": f"Top level error: {e}",
            "traceback": traceback.format_exc(),
            "step": "top_level"
        }

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
