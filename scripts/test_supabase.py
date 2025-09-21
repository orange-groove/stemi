#!/usr/bin/env python3
"""
Test script for Supabase integration
"""
import os
import tempfile
import soundfile as sf
import numpy as np
from supabase_integration import SupabaseStemStorage

def create_test_audio(filename: str, duration: float = 2.0):
    """Create a test audio file"""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Generate test tone
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4 note
    stereo_audio = np.column_stack([audio, audio])
    
    sf.write(filename, stereo_audio, sample_rate)
    print(f"Created test audio: {filename}")

def test_supabase_integration():
    """Test Supabase storage functionality"""
    
    # Check environment variables
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_ANON_KEY"):
        print("❌ Supabase environment variables not set")
        print("Please set SUPABASE_URL and SUPABASE_ANON_KEY")
        return False
    
    try:
        # Initialize Supabase storage
        print("🔧 Initializing Supabase storage...")
        storage = SupabaseStemStorage()
        print("✅ Supabase storage initialized")
        
        # Create test files
        print("🎵 Creating test audio files...")
        job_id = "test_job_123"
        test_files = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for stem in ["drums", "bass", "vocals", "other"]:
                filename = f"{temp_dir}/{stem}.wav"
                create_test_audio(filename)
                test_files[stem] = filename
            
            # Upload to Supabase
            print("📤 Uploading test files to Supabase...")
            public_urls = storage.upload_stems(job_id, test_files)
            
            print("✅ Upload successful!")
            print("📋 Public URLs:")
            for stem, url in public_urls.items():
                print(f"  {stem}: {url}")
            
            # Test getting URLs
            print("🔍 Testing URL retrieval...")
            retrieved_urls = storage.get_stem_urls(job_id)
            print(f"✅ Retrieved {len(retrieved_urls)} URLs")
            
            # Test cleanup
            print("🗑️ Testing cleanup...")
            storage.delete_stems(job_id)
            print("✅ Cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Supabase Integration")
    print("=" * 40)
    
    success = test_supabase_integration()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Tests failed!")
        print("\nMake sure to set your Supabase credentials:")
        print("export SUPABASE_URL='your_supabase_url'")
        print("export SUPABASE_ANON_KEY='your_supabase_key'")
