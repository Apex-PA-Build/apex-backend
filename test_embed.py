import google.generativeai as genai
from app.core.config import settings
genai.configure(api_key=settings.gemini_api_key)
r=genai.embed_content(model="models/text-embedding-004", content="hello")
print("text-embedding-004:", len(r['embedding']))
r2=genai.embed_content(model="models/gemini-embedding-001", content="hello")
print("gemini-embedding-001:", len(r2['embedding']))
