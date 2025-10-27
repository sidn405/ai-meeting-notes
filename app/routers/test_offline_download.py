#!/usr/bin/env python3
"""
Test script for offline meeting download functionality
Tests both HTML and ZIP download formats
"""

import requests
import sys
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to your API URL
LICENSE_KEY = "your-license-key-here"   # Change to your license key
MEETING_ID = 1                          # Change to test meeting ID

def test_download(meeting_id, format_type, license_key):
    """Test downloading a meeting in specified format"""
    
    url = f"{API_BASE_URL}/meetings/{meeting_id}/download-all"
    params = {"format": format_type}
    headers = {"X-License-Key": license_key}
    
    print(f"\n{'='*60}")
    print(f"Testing {format_type.upper()} download for meeting {meeting_id}")
    print(f"{'='*60}")
    
    try:
        print(f"Sending request to: {url}")
        print(f"Parameters: {params}")
        
        response = requests.get(url, params=params, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Determine file extension
            ext = 'html' if format_type == 'html' else 'zip'
            filename = f"meeting_{meeting_id}_test.{ext}"
            
            # Save file
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            print(f"✅ SUCCESS!")
            print(f"   File saved: {filename}")
            print(f"   File size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
            
            # Additional info for HTML
            if format_type == 'html':
                print(f"   Open in browser: file://{os.path.abspath(filename)}")
            
            # Additional info for ZIP
            if format_type == 'zip':
                try:
                    import zipfile
                    with zipfile.ZipFile(filename, 'r') as z:
                        print(f"   ZIP contents:")
                        for name in z.namelist():
                            info = z.getinfo(name)
                            print(f"      - {name} ({info.file_size:,} bytes)")
                except Exception as e:
                    print(f"   Could not read ZIP contents: {e}")
            
            return True
            
        elif response.status_code == 404:
            print(f"❌ FAILED: Meeting not found or no files available")
            try:
                error = response.json()
                print(f"   Error: {error.get('detail', 'Unknown error')}")
            except:
                pass
            return False
            
        elif response.status_code == 403:
            print(f"❌ FAILED: Not authorized")
            print(f"   Check your license key")
            return False
            
        elif response.status_code == 400:
            print(f"❌ FAILED: Bad request")
            try:
                error = response.json()
                detail = error.get('detail', 'Unknown error')
                print(f"   Error: {detail}")
                if 'cloud-stored' in detail.lower():
                    print(f"   Note: This meeting is in cloud storage")
                    print(f"   Use individual download endpoints instead")
            except:
                pass
            return False
            
        else:
            print(f"❌ FAILED: Unexpected error")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ FAILED: Cannot connect to API")
        print(f"   Check that the API is running at {API_BASE_URL}")
        return False
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False

def main():
    """Run all tests"""
    
    print("\n" + "="*60)
    print("OFFLINE MEETING DOWNLOAD - TEST SUITE")
    print("="*60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Meeting ID: {MEETING_ID}")
    print(f"License Key: {LICENSE_KEY[:20]}..." if len(LICENSE_KEY) > 20 else LICENSE_KEY)
    
    # Check configuration
    if LICENSE_KEY == "your-license-key-here":
        print("\n⚠️  WARNING: Please update LICENSE_KEY in the script")
        print("Edit this file and set your actual license key")
        return
    
    # Test HTML download
    html_success = test_download(MEETING_ID, "html", LICENSE_KEY)
    
    # Test ZIP download
    zip_success = test_download(MEETING_ID, "zip", LICENSE_KEY)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"HTML Download: {'✅ PASS' if html_success else '❌ FAIL'}")
    print(f"ZIP Download:  {'✅ PASS' if zip_success else '❌ FAIL'}")
    
    if html_success and zip_success:
        print(f"\n🎉 All tests passed!")
        print(f"\nGenerated files:")
        print(f"   - meeting_{MEETING_ID}_test.html")
        print(f"   - meeting_{MEETING_ID}_test.zip")
    else:
        print(f"\n⚠️  Some tests failed. Check the output above for details.")
    
    print()

if __name__ == "__main__":
    # Allow command line arguments
    if len(sys.argv) > 1:
        try:
            MEETING_ID = int(sys.argv[1])
        except ValueError:
            print(f"Invalid meeting ID: {sys.argv[1]}")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        LICENSE_KEY = sys.argv[2]
    
    if len(sys.argv) > 3:
        API_BASE_URL = sys.argv[3]
    
    main()