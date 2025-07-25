from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

@app.get("/")
async def health_check():
    return {"message": "Agent is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)