#!/usr/bin/env python3
"""
Super robust RunPod handler with exception catching at every level
This will help us identify exactly what's failing
"""

import runpod
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event):
    """
    Ultra-robust handler that catches everything and returns debug info
    """
    try:
        logger.info("=== ULTRA DEBUG HANDLER STARTED ===")
        
        # Test 1: Basic setup
        try:
            input_data = event.get("input", {})
            logger.info(f"✅ Input data received: {list(input_data.keys())}")
        except Exception as e:
            return {"error": f"Failed to get input data: {str(e)}", "step": "input_parsing"}
        
        # Test 2: Import all required packages
        try:
            import base64
            logger.info("✅ base64 imported")
            
            import torch
            logger.info(f"✅ torch imported - CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"✅ GPU: {torch.cuda.get_device_name(0)}")
            
            import torchaudio
            logger.info("✅ torchaudio imported")
            
            import tempfile
            import os
            import sys
            import glob
            import shutil
            from pathlib import Path
            logger.info("✅ Standard libraries imported")
            
            import demucs.separate
            logger.info("✅ demucs.separate imported")
            
            import soundfile as sf
            import numpy as np
            import io
            logger.info("✅ All audio processing libraries imported")
            
        except Exception as e:
            return {"error": f"Import failed: {str(e)}", "step": "imports", "traceback": traceback.format_exc()}
        
        # Test 3: Validate input
        try:
            if "audio_file" not in input_data:
                return {"error": "Missing audio_file in input", "step": "validation"}
            
            audio_b64 = input_data["audio_file"]
            logger.info(f"✅ Audio data length: {len(audio_b64)} chars")
            
            # Test base64 decode
            audio_data = base64.b64decode(audio_b64)
            logger.info(f"✅ Decoded audio size: {len(audio_data)} bytes")
            
        except Exception as e:
            return {"error": f"Audio validation failed: {str(e)}", "step": "audio_validation", "traceback": traceback.format_exc()}
        
        # Test 4: Create temp files
        try:
            temp_input_path = None
            temp_demucs_dir = None
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input_path = temp_input.name
            
            logger.info(f"✅ Created temp input: {temp_input_path}")
            
            temp_demucs_dir = tempfile.mkdtemp()
            logger.info(f"✅ Created temp output dir: {temp_demucs_dir}")
            
        except Exception as e:
            return {"error": f"Temp file creation failed: {str(e)}", "step": "temp_files", "traceback": traceback.format_exc()}
        
        # Test 5: Run Demucs
        try:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"✅ Using device: {device}")
            
            # Save original sys.argv
            original_argv = sys.argv.copy()
            
            # Set demucs arguments
            sys.argv = [
                'demucs.separate',
                '-n', 'htdemucs_6s',
                '-d', str(device),
                '-o', temp_demucs_dir,
                temp_input_path
            ]
            
            logger.info(f"✅ Demucs args set: {sys.argv}")
            
            # Run demucs
            logger.info("🎵 Starting Demucs separation...")
            demucs.separate.main()
            logger.info("✅ Demucs completed!")
            
            # Restore argv
            sys.argv = original_argv
            
        except Exception as e:
            # Make sure to restore argv even on error
            try:
                sys.argv = original_argv
            except:
                pass
            return {"error": f"Demucs processing failed: {str(e)}", "step": "demucs", "traceback": traceback.format_exc()}
        
        # Test 6: Find output files
        try:
            song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
            if not song_dirs:
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
            
            if not song_dirs:
                # List all files for debugging
                all_files = []
                for root, dirs, files in os.walk(temp_demucs_dir):
                    for file in files:
                        all_files.append(os.path.join(root, file))
                return {"error": "No Demucs output found", "step": "output_search", "all_files": all_files}
            
            demucs_output_dir = song_dirs[0]
            stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
            
            logger.info(f"✅ Found {len(stem_files)} stem files")
            
        except Exception as e:
            return {"error": f"Output file search failed: {str(e)}", "step": "output_search", "traceback": traceback.format_exc()}
        
        # Test 7: Process stems
        try:
            stems = input_data.get("stems", ["vocals", "bass", "drums", "other"])
            result_stems = {}
            
            # Map files to stems
            available_stems = {}
            for stem_file in stem_files:
                stem_name = Path(stem_file).stem
                available_stems[stem_name] = stem_file
            
            logger.info(f"✅ Available stems: {list(available_stems.keys())}")
            
            # Encode each requested stem
            for stem in stems:
                if stem in available_stems:
                    # Load and encode
                    stem_audio, sr = torchaudio.load(available_stems[stem])
                    stem_numpy = stem_audio.cpu().numpy()
                    if stem_numpy.shape[0] == 1:
                        stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                    
                    buffer = io.BytesIO()
                    sf.write(buffer, stem_numpy.T, sr, format='WAV')
                    buffer.seek(0)
                    
                    stem_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    result_stems[stem] = stem_b64
                    
                    logger.info(f"✅ Encoded {stem} stem ({len(stem_b64)} chars)")
            
            logger.info(f"✅ Successfully processed {len(result_stems)} stems")
            
        except Exception as e:
            return {"error": f"Stem processing failed: {str(e)}", "step": "stem_processing", "traceback": traceback.format_exc()}
        
        # Test 8: Cleanup
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
            # Don't fail the whole job for cleanup issues
        
        # Test 9: Create final response
        try:
            response = {
                "status": "completed",
                "stems": result_stems,
                "available_stems": list(available_stems.keys()),
                "debug_info": {
                    "device": str(device),
                    "cuda_available": torch.cuda.is_available(),
                    "stem_count": len(result_stems),
                    "total_files_found": len(stem_files)
                }
            }
            
            logger.info("✅ Final response created")
            logger.info(f"✅ Response keys: {list(response.keys())}")
            logger.info("=== ULTRA DEBUG HANDLER SUCCESS ===")
            
            return response
            
        except Exception as e:
            return {"error": f"Response creation failed: {str(e)}", "step": "response_creation", "traceback": traceback.format_exc()}
    
    except Exception as e:
        logger.error(f"=== TOP LEVEL EXCEPTION ===")
        logger.error(f"Error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "error": f"Top level handler error: {str(e)}", 
            "step": "top_level",
            "traceback": traceback.format_exc()
        }

# Initialize RunPod serverless
logger.info("=== STARTING ULTRA DEBUG RUNPOD HANDLER ===")
runpod.serverless.start({"handler": handler})
