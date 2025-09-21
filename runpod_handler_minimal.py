#!/usr/bin/env python3
"""
Minimal RunPod handler to test if basic output works
This will help us isolate if the issue is with return values or Demucs processing
"""

import runpod
import logging
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event):
    """
    Minimal test handler that just returns basic data
    """
    try:
        logger.info("=== MINIMAL HANDLER STARTED ===")
        
        input_data = event.get("input", {})
        logger.info(f"Input keys: {list(input_data.keys())}")
        
        # Create test response with fake stems data
        test_stems = {}
        for stem in ["vocals", "bass", "drums", "other"]:
            # Create small fake base64 data (just "test" encoded)
            fake_data = base64.b64encode(f"test-{stem}-data".encode()).decode()
            test_stems[stem] = fake_data
            logger.info(f"Created fake {stem} stem: {len(fake_data)} chars")
        
        response = {
            "status": "completed",
            "stems": test_stems,
            "available_stems": list(test_stems.keys()),
            "message": "minimal test successful"
        }
        
        logger.info(f"=== RETURNING MINIMAL RESPONSE ===")
        logger.info(f"Response keys: {list(response.keys())}")
        logger.info(f"Stems count: {len(test_stems)}")
        
        return response
        
    except Exception as e:
        logger.error(f"=== MINIMAL HANDLER ERROR ===")
        logger.error(f"Error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_response = {"error": f"Minimal handler error: {str(e)}"}
        logger.info(f"Returning error: {error_response}")
        return error_response

# Initialize RunPod serverless
logger.info("=== STARTING MINIMAL RUNPOD HANDLER ===")
runpod.serverless.start({"handler": handler})
