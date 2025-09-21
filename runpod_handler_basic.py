#!/usr/bin/env python3
"""
Most basic possible RunPod handler to test initialization
"""

import runpod

def handler(event):
    """
    Ultra-basic handler that just returns a simple message
    """
    return {"message": "basic handler works", "input_received": event.get("input", {})}

# Initialize RunPod serverless
runpod.serverless.start({"handler": handler})
