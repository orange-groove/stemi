#!/usr/bin/env python3
"""
Handler to test which imports are causing the issue
"""

import runpod

def handler(event):
    """
    Test imports one by one to find the problematic one
    """
    try:
        results = {}
        
        # Test 1: Basic imports
        try:
            import base64
            import os
            import sys
            results["basic_imports"] = "✅ OK"
        except Exception as e:
            return {"error": f"Basic imports failed: {e}", "step": "basic_imports"}
        
        # Test 2: PyTorch
        try:
            import torch
            results["torch_import"] = "✅ OK"
            results["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                results["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception as e:
            return {"error": f"PyTorch import failed: {e}", "step": "torch", "results": results}
        
        # Test 3: Audio processing
        try:
            import torchaudio
            results["torchaudio_import"] = "✅ OK"
        except Exception as e:
            return {"error": f"TorchAudio import failed: {e}", "step": "torchaudio", "results": results}
        
        try:
            import soundfile as sf
            import numpy as np
            results["audio_libs_import"] = "✅ OK"
        except Exception as e:
            return {"error": f"Audio libs import failed: {e}", "step": "audio_libs", "results": results}
        
        # Test 4: Demucs import (this might be the culprit)
        try:
            import demucs
            results["demucs_base_import"] = "✅ OK"
        except Exception as e:
            return {"error": f"Demucs base import failed: {e}", "step": "demucs_base", "results": results}
        
        try:
            import demucs.separate
            results["demucs_separate_import"] = "✅ OK"
        except Exception as e:
            return {"error": f"Demucs.separate import failed: {e}", "step": "demucs_separate", "results": results}
        
        # Test 5: Create a device (might cause memory issues)
        try:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            results["device_creation"] = f"✅ OK - {device}"
        except Exception as e:
            return {"error": f"Device creation failed: {e}", "step": "device", "results": results}
        
        # Test 6: Try to access Demucs models (this often downloads large files)
        try:
            # This might trigger model downloads
            from demucs.pretrained import get_model
            results["demucs_model_access"] = "✅ Accessible"
        except Exception as e:
            return {"error": f"Demucs model access failed: {e}", "step": "model_access", "results": results}
        
        return {
            "message": "All imports successful!",
            "results": results,
            "next_step": "Try actual processing"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {e}", "step": "unknown"}

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
