#!/usr/bin/env python3
"""
Test script for the stem separation service
"""

import requests
import time
import json
import sys
import os

def test_stem_separation(service_url, audio_file_path):
    """Test the stem separation endpoint with an audio file"""
    
    print(f"🎵 Testing Stem Separation Service")
    print(f"Service URL: {service_url}")
    print(f"Audio file: {audio_file_path}")
    print("=" * 50)
    
    # Check if file exists
    if not os.path.exists(audio_file_path):
        print(f"❌ Error: File not found: {audio_file_path}")
        return False
    
    # Get file size
    file_size = os.path.getsize(audio_file_path)
    print(f"📁 File size: {file_size / (1024*1024):.2f} MB")
    
    # Test health endpoint first
    print("\n🔍 Testing service health...")
    try:
        health_response = requests.get(f"{service_url}/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ Service is healthy")
            print(f"   GPU: {health_data.get('cuda_available', 'Unknown')}")
            print(f"   Device: {health_data.get('device', 'Unknown')}")
        else:
            print(f"❌ Health check failed: {health_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False
    
    # Upload and separate
    print(f"\n🚀 Starting stem separation...")
    print("⏳ This may take 1-3 minutes depending on file length...")
    
    try:
        with open(audio_file_path, 'rb') as f:
            files = {'file': (os.path.basename(audio_file_path), f, 'audio/mpeg')}
            data = {'stems': 'vocals,bass,drums,other'}  # Request specific stems
            
            start_time = time.time()
            response = requests.post(
                f"{service_url}/separate",
                files=files,
                data=data,
                timeout=300  # 5 minute timeout for processing
            )
            processing_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Separation completed in {processing_time:.1f} seconds!")
            print(f"📋 Job ID: {result.get('job_id')}")
            
            # Show available stems
            output_files = result.get('output_files', {})
            if output_files:
                print(f"\n🎼 Generated stems:")
                for stem_name, file_path in output_files.items():
                    print(f"   {stem_name}: {file_path}")
            
            # Show Supabase URLs if available
            supabase_urls = result.get('supabase_urls', {})
            if supabase_urls:
                print(f"\n☁️  Supabase URLs:")
                for stem_name, url in supabase_urls.items():
                    print(f"   {stem_name}: {url}")
            
            # Show download URLs
            job_id = result.get('job_id')
            if job_id:
                print(f"\n📥 Download URLs:")
                for stem_name in output_files.keys():
                    print(f"   {stem_name}: {service_url}/download/{job_id}/{stem_name}")
            
            return True
            
        else:
            print(f"❌ Separation failed: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (file may be too large or processing is slow)")
        return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False

def main():
    # Service URL - we'll try to detect the correct port
    base_ip = "50.173.192.54"
    possible_ports = [41218, 41180, 41174, 40425, 41030, 40420, 40512, 41257]
    
    service_url = None
    print("🔍 Detecting service port...")
    
    for port in possible_ports:
        test_url = f"http://{base_ip}:{port}"
        try:
            response = requests.get(f"{test_url}/health", timeout=3)
            if response.status_code == 200 and 'status' in response.json():
                service_url = test_url
                print(f"✅ Found service on port {port}")
                break
        except:
            continue
    
    if not service_url:
        print("❌ Could not find running service on any port")
        print("Please check that the service is running and update the port manually")
        return False
    
    # Audio file path
    audio_file = "/Users/adamgroves/Downloads/Bush - Letting the Cables Sleep.mp3"
    
    # Run the test
    success = test_stem_separation(service_url, audio_file)
    
    if success:
        print(f"\n🎉 Test completed successfully!")
        print(f"💡 You can now download the separated stems or access them via Supabase")
    else:
        print(f"\n❌ Test failed")
    
    return success

if __name__ == "__main__":
    main()
