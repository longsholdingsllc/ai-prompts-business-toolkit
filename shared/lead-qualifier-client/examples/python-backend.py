# Example: Python backend integration (for Income- and Field-service-AI- backends)
# Add to your FastAPI / Flask / server.py routes

import httpx  # or requests
from fastapi import APIRouter, Request  # adjust for your framework

router = APIRouter()
ENDPOINT = "https://live-lead-qualifier-agent.vercel.app/api/qualify"

@router.post("/qualify-lead")
async def qualify_lead(request: Request):
    lead = await request.json()

    async with httpx.AsyncClient() as client:
        response = await client.post(ENDPOINT, json=lead, timeout=10.0)
        result = response.json()

    # Optional: store in your database
    # await db.leads.insert({**lead, "score": result["score"], "action": result["recommended_action"]})

    return result
