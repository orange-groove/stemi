#!/usr/bin/env python3
"""
Local test script to isolate Demucs separation logic
This mimics the exact same process as the RunPod handler but runs locally
"""

import os
import sys
import tempfile
import shutil
import glob
import base64
import io
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_demucs_separation_local():
    """
    Test the exact same Demucs logic as in runpod_handler.py but locally
    """
    logger.info("=== STARTING LOCAL DEMUCS TEST ===")
    
    # Check if required packages are available
    try:
        import torch
        import torchaudio
        import demucs.separate
        import soundfile as sf
        import numpy as np
        logger.info("✅ All required packages imported successfully")
    except ImportError as e:
        logger.error(f"❌ Missing required package: {e}")
        logger.error("Install with: pip install torch torchaudio demucs soundfile numpy")
        return False
    
    # Check for test audio file
    test_file = "bush_30sec.mp3"
    if not os.path.exists(test_file):
        logger.error(f"❌ Test file {test_file} not found")
        logger.error("Create with: ffmpeg -i 'Bush - Letting the Cables Sleep.mp3' -t 30 bush_30sec.mp3")
        return False
    
    logger.info(f"✅ Test file found: {test_file}")
    
    # Initialize device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"🔥 Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")
        logger.info("💻 Using CPU (no CUDA available)")
    
    # Read and encode audio file (simulate API input)
    logger.info("📁 Reading test audio file...")
    with open(test_file, "rb") as f:
        audio_data = f.read()
    
    logger.info(f"📊 Audio file size: {len(audio_data)} bytes")
    
    # Encode to base64 (simulate API)
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
    logger.info(f"📝 Base64 encoded size: {len(audio_b64)} characters")
    
    # Decode back (simulate handler)
    decoded_audio = base64.b64decode(audio_b64)
    logger.info(f"🔄 Decoded audio size: {len(decoded_audio)} bytes")
    
    # Test the separation logic
    stems = ["vocals", "bass", "drums", "other"]
    result = separate_stems_local(decoded_audio, stems, device)
    
    if result["success"]:
        logger.info("🎉 LOCAL TEST SUCCESSFUL!")
        logger.info(f"✅ Generated stems: {list(result['stems'].keys())}")
        logger.info(f"📊 Stems data sizes:")
        for stem_name, stem_b64 in result["stems"].items():
            size_kb = len(base64.b64decode(stem_b64)) / 1024
            logger.info(f"   {stem_name}: {size_kb:.1f} KB")
        return True
    else:
        logger.error("❌ LOCAL TEST FAILED!")
        logger.error(f"Error: {result['error']}")
        return False

def separate_stems_local(audio_data: bytes, stems: list, device) -> dict:
    """
    Local version of the separation logic from runpod_handler.py
    """
    result = {"success": False, "error": "Unknown error"}
    temp_input_path = None
    temp_demucs_dir = None
    
    try:
        logger.info("=== SEPARATE_STEMS LOCAL STARTED ===")
        logger.info(f"Audio data size: {len(audio_data)} bytes")
        logger.info(f"Requested stems: {stems}")
        logger.info(f"Device: {device}")
        
        # Create temporary file for input audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name
        
        logger.info(f"Created temp file: {temp_input_path}")
        
        # Create temporary directory for demucs output
        temp_demucs_dir = tempfile.mkdtemp()
        logger.info(f"Created temp output dir: {temp_demucs_dir}")
        
        # Prepare demucs arguments
        original_argv = sys.argv.copy()
        try:
            sys.argv = [
                'demucs.separate',
                '-n', 'htdemucs_6s',
                '-d', str(device),
                '-o', temp_demucs_dir,
                temp_input_path
            ]
            
            logger.info(f"Demucs args: {sys.argv}")
            
            # Run demucs separation
            logger.info("🎵 Running Demucs separation...")
            import demucs.separate
            demucs.separate.main()
            logger.info("✅ Demucs separation completed")
            
            # Find output files
            logger.info(f"🔍 Searching for output in: {temp_demucs_dir}")
            song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs_6s', '*'))
            logger.info(f"Found htdemucs_6s dirs: {song_dirs}")
            
            if not song_dirs:
                song_dirs = glob.glob(os.path.join(temp_demucs_dir, 'htdemucs', '*'))
                logger.info(f"Found htdemucs dirs: {song_dirs}")
            
            if not song_dirs:
                logger.error("No Demucs output directories found")
                # List all files in temp dir for debugging
                all_files = []
                for root, dirs, files in os.walk(temp_demucs_dir):
                    for file in files:
                        all_files.append(os.path.join(root, file))
                logger.error(f"All files in temp dir: {all_files}")
                raise ValueError("No Demucs output found")
            
            demucs_output_dir = song_dirs[0]
            logger.info(f"📁 Using output dir: {demucs_output_dir}")
            
            stem_files = glob.glob(os.path.join(demucs_output_dir, '*.wav'))
            logger.info(f"🎼 Found {len(stem_files)} stem files: {[os.path.basename(f) for f in stem_files]}")
            
            # Map stem files to requested stems
            available_stems = {}
            for stem_file in stem_files:
                stem_name = Path(stem_file).stem
                available_stems[stem_name] = stem_file
            
            logger.info(f"🗂️ Available stems: {list(available_stems.keys())}")
            
            # Encode stems as base64
            result_stems = {}
            for stem in stems:
                if stem in available_stems:
                    logger.info(f"🎯 Processing {stem} stem...")
                    
                    # Load the stem audio
                    import torchaudio
                    stem_audio, sr = torchaudio.load(available_stems[stem])
                    
                    # Convert to numpy and ensure stereo
                    import numpy as np
                    stem_numpy = stem_audio.cpu().numpy()
                    if stem_numpy.shape[0] == 1:
                        stem_numpy = np.repeat(stem_numpy, 2, axis=0)
                    
                    # Save to bytes buffer as WAV
                    buffer = io.BytesIO()
                    import soundfile as sf
                    sf.write(buffer, stem_numpy.T, sr, format='WAV')
                    buffer.seek(0)
                    
                    # Encode as base64
                    stem_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    result_stems[stem] = stem_b64
                    
                    logger.info(f"✅ Encoded {stem} stem ({len(stem_b64)} chars)")
                else:
                    logger.warning(f"⚠️ Requested stem '{stem}' not found in output")
            
            result = {
                "success": True,
                "stems": result_stems,
                "available_stems": list(available_stems.keys())
            }
            logger.info(f"=== LOCAL SEPARATION SUCCESS ===")
            logger.info(f"Result stems count: {len(result_stems)}")
            logger.info(f"Available stems: {result['available_stems']}")
            
        finally:
            # Restore sys.argv
            sys.argv = original_argv
            
            # Clean up temporary files safely
            try:
                if temp_input_path and os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
                    logger.info("🧹 Cleaned up temp input file")
            except:
                pass
            try:
                if temp_demucs_dir and os.path.exists(temp_demucs_dir):
                    shutil.rmtree(temp_demucs_dir)
                    logger.info("🧹 Cleaned up temp output dir")
            except:
                pass
            
            # Clear GPU memory
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("🧹 Cleared GPU memory")
        
        logger.info(f"=== RETURNING LOCAL RESULT ===")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result success: {result.get('success', 'unknown')}")
        return result
    
    except Exception as e:
        logger.error(f"=== LOCAL SEPARATION EXCEPTION ===")
        logger.error(f"Exception: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        logger.info(f"Returning error result: {error_result}")
        return error_result

if __name__ == "__main__":
    print("🧪 Testing Demucs separation locally...")
    print("This will help identify if the issue is with Demucs or RunPod integration.")
    print()
    
    success = test_demucs_separation_local()
    
    print()
    if success:
        print("🎉 LOCAL TEST PASSED! The Demucs logic works fine.")
        print("   → The issue is likely in the RunPod integration or environment.")
    else:
        print("❌ LOCAL TEST FAILED! There's an issue with the Demucs logic.")
        print("   → Fix the local logic before testing on RunPod.")
