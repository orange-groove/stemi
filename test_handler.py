"""
Simple test handler for debugging RunPod issues
"""
import runpod
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_handler(event):
    """Simple test handler that just echoes input"""
    try:
        logger.info(f"Received event: {event}")
        
        input_data = event.get("input", {})
        
        if "audio_file" not in input_data:
            return {"error": "Missing audio_file in input"}
        
        stems = input_data.get("stems", ["vocals", "bass", "drums", "other"])
        
        # Just return a simple response for testing
        return {
            "status": "completed",
            "message": "Test handler working",
            "received_stems": stems,
            "audio_size": len(input_data.get("audio_file", "")),
            "test_data": "This is a test response"
        }
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}

# Initialize RunPod serverless
runpod.serverless.start({"handler": test_handler})
