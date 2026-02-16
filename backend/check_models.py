import os
import sys
from dotenv import load_dotenv
from google import genai

load_dotenv('.env')

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("Error: GOOGLE_API_KEY not found.")
    sys.exit(1)

print(f"Checking models...")

try:
    client = genai.Client(api_key=api_key)
    # The new SDK 0.3+ / 1.x often behaves differently.
    # The response is usually a list of Model objects, each having a 'name' field.
    for m in client.models.list():
        # Just print the name to be safe
        print(f"- {m.name}")
            
except Exception as e:
    print(f"Error listing models: {e}")
