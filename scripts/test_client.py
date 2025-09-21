#!/usr/bin/env python3
"""
Test client for the STEMI Separation Service
"""
import requests
import time
import os
import argparse
from pathlib import Path

def test_health(base_url: str):
    """Test health endpoints"""
    print("Testing health endpoints...")
    
    # Basic health check
    try:
        response = requests.get(f"{base_url}/")
        print(f"✓ Basic health: {response.status_code}")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"✗ Basic health failed: {e}")
    
    # Detailed health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✓ Detailed health: {response.status_code}")
        health_data = response.json()
        print(f"  Device: {health_data.get('device')}")
        print(f"  CUDA Available: {health_data.get('cuda_available')}")
        print(f"  Model Loaded: {health_data.get('model_loaded')}")
        if health_data.get('gpu_memory'):
            print(f"  GPU Memory: {health_data.get('gpu_memory') / 1024**3:.1f} GB")
    except Exception as e:
        print(f"✗ Detailed health failed: {e}")

def test_separation(base_url: str, audio_file: str, stems: str = None):
    """Test stem separation"""
    print(f"\nTesting stem separation with {audio_file}...")
    
    if not os.path.exists(audio_file):
        print(f"✗ Audio file not found: {audio_file}")
        return None
    
    # Prepare request
    files = {"file": open(audio_file, "rb")}
    data = {}
    if stems:
        data["stems"] = stems
    
    try:
        # Upload and separate
        print("Uploading file...")
        response = requests.post(f"{base_url}/separate", files=files, data=data)
        files["file"].close()
        
        if response.status_code != 200:
            print(f"✗ Separation failed: {response.status_code}")
            print(f"  Error: {response.text}")
            return None
        
        result = response.json()
        print(f"✓ Separation completed")
        print(f"  Job ID: {result['job_id']}")
        print(f"  Stems: {result['stems']}")
        print(f"  Output files: {list(result['output_files'].keys())}")
        
        return result['job_id']
        
    except Exception as e:
        print(f"✗ Separation failed: {e}")
        return None

def test_download(base_url: str, job_id: str):
    """Test downloading stems"""
    print(f"\nTesting stem downloads for job {job_id}...")
    
    try:
        # Get job status
        response = requests.get(f"{base_url}/jobs/{job_id}")
        if response.status_code != 200:
            print(f"✗ Failed to get job status: {response.status_code}")
            return
        
        job_data = response.json()
        print(f"✓ Job status retrieved")
        print(f"  Available stems: {job_data['available_stems']}")
        
        # Download each stem
        for stem in job_data['available_stems']:
            try:
                download_url = f"{base_url}/download/{job_id}/{stem}"
                response = requests.get(download_url)
                
                if response.status_code == 200:
                    filename = f"downloaded_{stem}.wav"
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    print(f"✓ Downloaded {stem} -> {filename}")
                else:
                    print(f"✗ Failed to download {stem}: {response.status_code}")
                    
            except Exception as e:
                print(f"✗ Download failed for {stem}: {e}")
        
    except Exception as e:
        print(f"✗ Download test failed: {e}")

def test_cleanup(base_url: str, job_id: str):
    """Test job cleanup"""
    print(f"\nTesting job cleanup for {job_id}...")
    
    try:
        response = requests.delete(f"{base_url}/jobs/{job_id}")
        if response.status_code == 200:
            print("✓ Job deleted successfully")
        else:
            print(f"✗ Failed to delete job: {response.status_code}")
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")

def create_test_audio(filename: str, duration: float = 5.0):
    """Create a test audio file"""
    try:
        import numpy as np
        import soundfile as sf
        
        # Generate a simple test tone
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Mix of different frequencies to simulate different instruments
        audio = (
            0.3 * np.sin(2 * np.pi * 440 * t) +  # A4 note
            0.2 * np.sin(2 * np.pi * 880 * t) +  # A5 note
            0.1 * np.sin(2 * np.pi * 220 * t) +  # A3 note
            0.1 * np.random.randn(len(t))         # Noise
        )
        
        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8
        
        # Save as stereo
        stereo_audio = np.column_stack([audio, audio])
        sf.write(filename, stereo_audio, sample_rate)
        
        print(f"✓ Created test audio: {filename}")
        return True
        
    except ImportError:
        print("✗ soundfile not available, cannot create test audio")
        return False
    except Exception as e:
        print(f"✗ Failed to create test audio: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test STEMI Separation Service")
    parser.add_argument("--url", default="http://localhost:8000", help="Service URL")
    parser.add_argument("--audio", help="Audio file to test with")
    parser.add_argument("--stems", help="Comma-separated list of stems")
    parser.add_argument("--create-test", action="store_true", help="Create test audio file")
    parser.add_argument("--cleanup", action="store_true", help="Clean up test files")
    
    args = parser.parse_args()
    
    base_url = args.url.rstrip("/")
    
    # Create test audio if requested
    if args.create_test:
        test_file = "test_audio.wav"
        if create_test_audio(test_file):
            args.audio = test_file
    
    # Run tests
    test_health(base_url)
    
    if args.audio:
        job_id = test_separation(base_url, args.audio, args.stems)
        
        if job_id:
            test_download(base_url, job_id)
            
            if args.cleanup:
                test_cleanup(base_url, job_id)
    
    # Clean up test files
    if args.cleanup:
        for file in ["test_audio.wav", "downloaded_drums.wav", "downloaded_bass.wav", 
                    "downloaded_vocals.wav", "downloaded_other.wav"]:
            if os.path.exists(file):
                os.remove(file)
                print(f"✓ Cleaned up {file}")

if __name__ == "__main__":
    main()
