"""
Task Management + SSE Stream
- GET  /api/tasks          — List all tasks
- POST /api/tasks          — Create new task
- GET  /api/tasks/{id}     — Get single task
- POST /api/tasks/{id}/trigger — Research + trigger outbound call
- GET  /api/events         — SSE stream for dashboard
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from models.schemas import TaskCreate, SSEEvent, SSEEventType
from services.task_store import store
from services import tavily_service, vapi_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Task CRUD ────────────────────────────────────────────────

@router.get("/api/tasks")
async def list_tasks():
    tasks = store.list_tasks()
    return [t.model_dump() for t in tasks]


@router.post("/api/tasks")
async def create_task(task_create: TaskCreate):
    task = store.create_task(task_create)
    return task.model_dump()


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()


# ── Trigger Call ─────────────────────────────────────────────

@router.post("/api/tasks/{task_id}/trigger")
async def trigger_task(task_id: str):
    """Research the task, then trigger Vapi outbound call."""
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Step 1: Research via Tavily
    store.update_task(task_id, status="researching")
    await store.push_task_update(task)

    research = tavily_service.research_for_task(
        company=task.company,
        action=task.action.value,
        service_type=task.service_type or "",
    )
    store.update_task(
        task_id,
        research_context=research["context"],
        research_sources=research["sources"],
    )

    # Step 2: Trigger Vapi outbound call
    store.update_task(task_id, status="calling")
    task = store.get_task(task_id)  # Refresh
    await store.push_task_update(task)

    call_result = await vapi_service.trigger_outbound_call(
        phone_number=task.phone_number,
        task_id=task_id,
        user_name=task.user_name,
        company=task.company,
        objective=task.action.value,
        current_rate=task.current_rate or 0,
        target_rate=task.target_rate or 0,
        research_context=research["context"],
    )

    if "error" in call_result:
        store.update_task(task_id, status="failed", outcome=call_result["error"])
        task = store.get_task(task_id)
        await store.push_task_update(task)
        return {"status": "error", "detail": call_result["error"]}

    # Link the Vapi call ID to our task
    vapi_call_id = call_result.get("id", "")
    store.update_task(task_id, call_id=vapi_call_id)

    return {
        "status": "calling",
        "call_id": vapi_call_id,
        "task_id": task_id,
        "research": research,
    }


# ── SSE Stream ───────────────────────────────────────────────

@router.get("/api/events")
async def sse_stream(request: Request):
    """Server-Sent Events stream for real-time dashboard updates."""

    async def event_generator():
        # Send initial state
        tasks = store.list_tasks()
        yield _format_sse(SSEEvent(
            type=SSEEventType.TASK_UPDATED,
            data={"tasks": [t.model_dump() for t in tasks]},
        ))

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(store.event_queue.get(), timeout=15.0)
                yield _format_sse(event)
            except asyncio.TimeoutError:
                # Send keepalive to prevent connection timeout
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: SSEEvent) -> str:
    data = json.dumps(event.model_dump())
    return f"event: {event.type.value}\ndata: {data}\n\n"


# ── Admin: Update Vapi URLs ─────────────────────────────────

@router.post("/api/admin/update-vapi-urls")
async def update_vapi_urls(request: Request):
    """After deploying to Render, call this to update all Vapi URLs."""
    body = await request.json()
    base_url = body.get("base_url", "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url required")

    # Update assistant server URL
    assistant_result = await vapi_service.update_assistant_server_url(base_url)

    # Update all tool server URLs
    tool_results = await vapi_service.update_tool_server_urls(base_url)

    return {
        "assistant": assistant_result,
        "tools": tool_results,
    }
