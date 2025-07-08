#!/usr/bin/env python3
"""Debug authentication issue."""

from ai_polling.core.config import get_config
from ai_polling.extractors.pdf_extractor import PDFExtractor
from pathlib import Path

def debug_auth():
    print("=== Testing Authentication ===")
    
    # Test config loading
    config = get_config()
    print(f"API Key from config: {config.api.google_api_key[:10]}...{config.api.google_api_key[-4:]}")
    print(f"Model: {config.api.model_name}")
    
    # Test extractor initialization
    try:
        extractor = PDFExtractor()
        print("✅ PDF Extractor initialized successfully")
        print(f"Client: {extractor.client}")
        
        # Test a simple API call
        from google import genai
        from google.genai import types
        
        response = extractor.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Say hello in one word"]
        )
        
        print(f"✅ Simple API call works: {response.text}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        
        # Print more details
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_auth()