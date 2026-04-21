from pydantic import BaseModel


class DailyBrief(BaseModel):
    greeting: str
    narrative: str
    focus_recommendation: str
    risks: list[str]
    quick_wins: list[str]
    mood_prompt: str


class MoodCheckin(BaseModel):
    mood: str  # energetic | focused | good | tired | stressed
