# test_auto_download.py
import requests
import time

BASE_URL = "http://localhost:8000"
LICENSE_KEY = "free-tier-test-key"

# 1. Upload a file as Free tier
files = {"file": open("test.mp3", "rb")}
data = {"title": "Auto-Download Test", "email_to": "test@example.com"}
headers = {"X-License-Key": LICENSE_KEY}

response = requests.post(
    f"{BASE_URL}/meetings/upload",
    files=files,
    data=data,
    headers=headers
)

meeting_id = response.json()["id"]
print(f"Created meeting: {meeting_id}")

# 2. Wait for processing
while True:
    status_response = requests.get(
        f"{BASE_URL}/meetings/{meeting_id}/status",
        headers=headers
    )
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status == "ready_for_download":
        print("✅ Ready for auto-download!")
        break
    
    time.sleep(5)

# 3. Simulate frontend download
print("Downloading transcript...")
transcript_response = requests.get(
    f"{BASE_URL}/meetings/{meeting_id}/download?type=transcript",
    headers=headers
)
print("Downloaded transcript")

print("Downloading summary...")
summary_response = requests.get(
    f"{BASE_URL}/meetings/{meeting_id}/download?type=summary",
    headers=headers
)
print("Downloaded summary")

# 4. Confirm download complete
confirm_response = requests.post(
    f"{BASE_URL}/meetings/{meeting_id}/confirm-download",
    headers=headers
)
print(f"Confirmation: {confirm_response.json()}")

# 5. Verify files deleted from server
final_status = requests.get(
    f"{BASE_URL}/meetings/{meeting_id}/status",
    headers=headers
)
print(f"Final status: {final_status.json()}")