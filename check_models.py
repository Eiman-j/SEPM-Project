import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# If load_dotenv doesn't work, paste your key directly below:
api_key = os.getenv("GEMINI_API_KEY") 
# api_key = "PASTE_YOUR_REAL_KEY_HERE_IF_NEEDED"

genai.configure(api_key=api_key)

print("Listing available models...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"Name: {m.name}")