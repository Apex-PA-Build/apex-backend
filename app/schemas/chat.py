from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to the assistant.")
    
class ChatResponse(BaseModel):
    reply: str = Field(..., description="The assistant's conversational reply.")
