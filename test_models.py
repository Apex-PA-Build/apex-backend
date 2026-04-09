import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.gemini_api_key)
for m in genai.list_models():
    print(m.name, m.supported_generation_methods)
