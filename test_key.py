import os
import asyncio
import google.generativeai as genai

async def main():
    api_key = "AQ.Ab8RN6LP-iQkj9gctd121-t3pCN2lCLz3iJt7MS2zYv9a4vRSg"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = await model.generate_content_async("Hello")
        print("Success:", response.text)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
