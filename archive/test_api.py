#!/usr/bin/env python3
"""Simple test script to verify Google Gemini API key."""

import os
from google import genai
from dotenv import load_dotenv

def test_api_key():
    # Load .env file
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ GOOGLE_API_KEY environment variable not set")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        
        # Simple test call
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Say hello"]
        )
        
        if response and response.text:
            print("✅ API Key is valid!")
            print(f"Response: {response.text}")
            return True
        else:
            print("❌ No response from API")
            return False
            
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False

if __name__ == "__main__":
    test_api_key()