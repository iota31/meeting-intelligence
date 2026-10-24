import requests
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import get_settings, update_settings

TEST_API_BASE_URL = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

def test_settings_api():
    url = f"{TEST_API_BASE_URL}/api/settings"
    
    # 1. Save original settings directly from DB to avoid masked keys
    original_db_settings = get_settings()
    
    try:
        # 2. GET initial settings via API
        res = requests.get(url, timeout=5)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        # 3. POST update settings
        payload = {
            "service_mode": "cloud",
            "deepgram_api_key": "dg_test_key",
            "groq_api_key": "gq_test_key"
        }
        res = requests.post(url, json=payload, timeout=5)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        # 4. GET verify settings
        res = requests.get(url, timeout=5)
        assert res.status_code == 200
        data = res.json()
        assert data["service_mode"] == "cloud"
        assert data["deepgram_api_key"] == "dg_..._key"
        assert data["groq_api_key"] == "..._key"
    finally:
        # 5. Restore original settings to DB
        update_settings(
            original_db_settings["service_mode"],
            original_db_settings["deepgram_api_key"],
            original_db_settings["groq_api_key"]
        )
