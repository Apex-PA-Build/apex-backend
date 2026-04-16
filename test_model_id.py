import asyncio
import anthropic
from app.core.config import settings

async def main():
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=1.0,
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print("SUCCESS! Model used:", response.model)
        for block in response.content:
            if block.type == 'text':
                print("Output:", block.text)
    except Exception as e:
        print("ERROR:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
