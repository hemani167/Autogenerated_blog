import os
import google.generativeai as genai

os.environ["GOOGLE_API_KEY"] = "AIzaSyAoYFAFAj76YZVXgAj6Dsh4Njt5lLn-3Js"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

try:
    print("Available models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
