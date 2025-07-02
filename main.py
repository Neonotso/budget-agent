from fastapi import FastAPI
import uvicorn
from livekit.agents import AgentSession, Agent, function_tool
from livekit.plugins import openai, noise_cancellation

from budget_tools import BudgetSheetsManager

import asyncio
import os

app = FastAPI()

# Define your agent
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")
        self.budget_manager = BudgetSheetsManager()

    # Include your @function_tool methods here...

# Global session variable
session = None

@app.on_event("startup")
async def startup_event():
    print("Starting up FastAPI app...")
    global session
    session = AgentSession(
        agent=Assistant(),
        llm=openai.realtime.RealtimeModel(voice="coral")
    )
    asyncio.create_task(session.run())

@app.get("/")
async def health_check():
    return {"message": "Agent is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
