import asyncio
from app.core.config import settings
import anthropic

async def run():
    print(f"API Key starts with: {settings.anthropic_api_key[:10]}... (Len: {len(settings.anthropic_api_key)})")
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=10,
            messages=[{"role": "user", "content": "hello"}]
        )
        print(response)
    except Exception as e:
        print(repr(e))

if __name__ == "__main__":
    asyncio.run(run())
