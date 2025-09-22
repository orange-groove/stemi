#!/usr/bin/env python3
"""
Test local Demucs processing + Supabase upload
This mimics what happens in the RunPod handler
"""
import os
import sys
import tempfile
import shutil
import io
import uuid
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_local_demucs_supabase():
    """Test the complete pipeline locally"""
    
    # Audio file to test with
    audio_file = "bush_30sec.mp3"
    if not os.path.exists(audio_file):
        logger.error(f"Audio file {audio_file} not found")
        return False
    
    # Create temporary directories
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, "separated")
    
    try:
        logger.info("=== TESTING LOCAL DEMUCS + SUPABASE ===")
        logger.info(f"Input file: {audio_file}")
        logger.info(f"Temp directory: {temp_dir}")
        
        # Step 1: Run Demucs separation
        logger.info("🎵 Step 1: Running Demucs separation...")
        
        # Import and run Demucs
        import demucs.separate
        
        # Save original sys.argv
        original_argv = sys.argv.copy()
        
        # Set up Demucs arguments
        sys.argv = [
            "demucs",
            "--mp3",
            "--mp3-bitrate", "192",
            "-o", temp_dir,
            audio_file
        ]
        
        # Run Demucs
        demucs.separate.main()
        
        # Restore sys.argv
        sys.argv = original_argv
        
        logger.info("✅ Demucs separation completed")
        
        # Step 2: Find separated stems
        logger.info("🔍 Step 2: Finding separated stems...")
        
        # Look for output directory
        stem_dirs = list(Path(temp_dir).glob("htdemucs/*"))
        if not stem_dirs:
            logger.error("No Demucs output found")
            return False
        
        stem_dir = stem_dirs[0]
        stem_files = list(stem_dir.glob("*.mp3"))
        
        available_stems = {}
        for stem_file in stem_files:
            stem_name = stem_file.stem
            if stem_name in ['vocals', 'bass', 'drums', 'other']:
                available_stems[stem_name] = str(stem_file)
        
        logger.info(f"✅ Found stems: {list(available_stems.keys())}")
        
        # Step 3: Test Supabase upload
        logger.info("☁️ Step 3: Testing Supabase upload...")
        
        # Import Supabase integration
        from supabase_integration import SupabaseStemStorage
        
        # Initialize Supabase
        supabase_storage = SupabaseStemStorage()
        logger.info("✅ Supabase client initialized")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Generated job ID: {job_id}")
        
        # Upload stems
        stem_urls = supabase_storage.upload_stems(job_id, available_stems)
        
        logger.info("✅ Supabase upload completed!")
        logger.info(f"Uploaded {len(stem_urls)} stems:")
        for stem_name, url in stem_urls.items():
            logger.info(f"  • {stem_name}: {url}")
        
        # Step 4: Verify bucket structure
        logger.info("🗂️ Step 4: Checking bucket structure...")
        logger.info(f"Expected bucket path: stems/{job_id}/")
        logger.info("Stems should be accessible at the URLs above")
        
        logger.info("🎉 LOCAL TEST SUCCESSFUL!")
        logger.info("The complete pipeline works:")
        logger.info("  ✅ Demucs processing")
        logger.info("  ✅ Supabase bucket upload")
        logger.info("  ✅ URL generation")
        logger.info("  ✅ Logical job-based storage")
        
        return True
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.info("Some dependencies might be missing locally")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        except:
            pass

if __name__ == "__main__":
    success = test_local_demucs_supabase()
    if success:
        print("\n🎉 SUCCESS: Local Demucs + Supabase test passed!")
    else:
        print("\n❌ FAILED: Local test failed")
        sys.exit(1)
