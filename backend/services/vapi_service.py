import logging

import httpx

import config

logger = logging.getLogger(__name__)

VAPI_BASE = "https://api.vapi.ai"


async def trigger_outbound_call(
    phone_number: str,
    task_id: str,
    user_name: str = "Neel",
    company: str = "",
    objective: str = "",
    current_rate: float = 0,
    target_rate: float = 0,
    research_context: str = "",
) -> dict:
    """Trigger a Vapi outbound call with task-specific overrides."""
    if not config.VAPI_API_KEY:
        return {"error": "VAPI_API_KEY not set"}
    if not config.VAPI_PHONE_NUMBER_ID:
        return {"error": "VAPI_PHONE_NUMBER_ID not set — buy a number in Vapi dashboard"}

    payload = {
        "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
        "assistantId": config.VAPI_ASSISTANT_ID,
        "customer": {"number": phone_number},
        "assistantOverrides": {
            "variableValues": {
                "taskId": task_id,
                "customerName": user_name,
                "targetCompany": company,
                "objective": objective,
                "currentRate": str(current_rate),
                "targetRate": str(target_rate),
                "researchContext": research_context[:500],  # Keep it short for voice
            }
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{VAPI_BASE}/call",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config.VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("Outbound call triggered: %s", data.get("id"))
            return data
        except httpx.HTTPStatusError as e:
            logger.error("Vapi call failed: %s %s", e.response.status_code, e.response.text)
            return {"error": e.response.text}
        except Exception as e:
            logger.error("Vapi call error: %s", e)
            return {"error": str(e)}


async def update_assistant_server_url(new_url: str) -> dict:
    """Update the assistant's server URL (used after Render deploy)."""
    if not config.VAPI_API_KEY:
        return {"error": "VAPI_API_KEY not set"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.patch(
                f"{VAPI_BASE}/assistant/{config.VAPI_ASSISTANT_ID}",
                json={"serverUrl": f"{new_url}/api/vapi/webhook"},
                headers={
                    "Authorization": f"Bearer {config.VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to update assistant URL: %s", e)
            return {"error": str(e)}


async def update_tool_server_urls(new_url: str) -> list[dict]:
    """Update all 5 tool server URLs to point to new backend."""
    tool_ids = config.VAPI_TOOL_IDS
    if not tool_ids:
        logger.warning("VAPI_TOOL_IDS not set — skipping tool URL updates")
        return []
    results = []
    async with httpx.AsyncClient() as client:
        for tool_id in tool_ids:
            try:
                resp = await client.patch(
                    f"{VAPI_BASE}/tool/{tool_id}",
                    json={"server": {"url": f"{new_url}/api/vapi/tool-call"}},
                    headers={
                        "Authorization": f"Bearer {config.VAPI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                results.append({"tool_id": tool_id, "status": "updated"})
            except Exception as e:
                results.append({"tool_id": tool_id, "error": str(e)})
    return results
