import requests
import os
import time

TEST_API_BASE_URL = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

def test_async_audio_upload(tmp_path):
    # Create a fake tiny wave file for upload
    fake_wav = tmp_path / "test.wav"
    # standard minimal wav header (44 bytes)
    header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    fake_wav.write_bytes(header)
    
    url = f"{TEST_API_BASE_URL}/api/meetings/upload/audio"
    
    with open(fake_wav, "rb") as f:
        files = {"file": ("test.wav", f, "audio/wav")}
        res = requests.post(url, files=files)
        
    assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
    data = res.json()
    assert "meeting_id" in data
    assert data["status"] == "processing"
    
    meeting_id = data["meeting_id"]
    
    # Check meeting list to ensure it's there with processing status
    res = requests.get(f"{TEST_API_BASE_URL}/api/meetings")
    assert res.status_code == 200
    meetings = res.json()
    found = next((m for m in meetings if m["id"] == meeting_id), None)
    assert found is not None
    assert found["status"] == "processing"
    assert found["turn_count"] == 0
