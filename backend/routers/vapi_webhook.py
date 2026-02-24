"""
Vapi Webhook Handler
POST /api/vapi/webhook

Receives ALL Vapi server messages:
- end-of-call-report: Full transcript + analysis after call ends
- status-update: Call state changes (ringing, in-progress, ended)
- transcript: Real-time partial transcripts
- conversation-update: Full conversation history
- speech-update: Speech activity events

From Vapi docs: Always return HTTP 200, even for errors.
"""

import logging

from fastapi import APIRouter, Request

from models.schemas import SSEEvent, SSEEventType
from services.task_store import store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/vapi/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type", "")
    call_obj = message.get("call", {})
    call_id = call_obj.get("id", "unknown")

    logger.info("Webhook: type=%s call=%s", msg_type, call_id)

    if msg_type == "end-of-call-report":
        await _handle_end_of_call(message, call_id)

    elif msg_type == "status-update":
        await _handle_status_update(message, call_id)

    elif msg_type == "transcript":
        await _handle_transcript(message, call_id)

    elif msg_type == "conversation-update":
        # Full conversation — we mainly care about transcript events
        pass

    elif msg_type == "speech-update":
        await _handle_speech_update(message, call_id)

    # Always return 200
    return {"status": "ok"}


async def _handle_end_of_call(message: dict, call_id: str):
    """Process end-of-call report with full transcript and analysis."""
    transcript = message.get("transcript", "")
    summary = message.get("summary", "")
    ended_reason = message.get("endedReason", "")
    analysis = message.get("analysis", {})
    structured_data = analysis.get("structuredData", {})

    logger.info(
        "Call ended: reason=%s summary=%s",
        ended_reason,
        summary[:100] if summary else "none",
    )

    # Update the linked task
    for task in store.list_tasks():
        if task.call_id == call_id:
            task_completed = structured_data.get("task_completed", False)
            outcome = structured_data.get("outcome", summary or "Call ended")
            savings = structured_data.get("savings_amount", 0)
            conf = structured_data.get("confirmation_number", "")

            new_status = "completed" if task_completed else "needs_followup"

            store.update_task(
                task.id,
                status=new_status,
                outcome=outcome,
                savings=savings,
                confirmation_number=conf or task.confirmation_number,
            )
            await store.push_task_update(task)
            break

    # Push full report to SSE
    await store.push_event(SSEEvent(
        type=SSEEventType.CALL_STATUS,
        data={
            "call_id": call_id,
            "status": "ended",
            "ended_reason": ended_reason,
            "summary": summary,
            "structured_data": structured_data,
            "transcript": transcript[:2000],  # Truncate for SSE
        },
    ))


async def _handle_status_update(message: dict, call_id: str):
    """Track call state: ringing, in-progress, ended."""
    status = message.get("status", "")

    logger.info("Call status: %s → %s", call_id, status)

    # Update task status based on call state
    if status == "in-progress":
        for task in store.list_tasks():
            if task.call_id == call_id:
                store.update_task(task.id, status="calling")
                await store.push_task_update(task)
                break

    await store.push_event(SSEEvent(
        type=SSEEventType.CALL_STATUS,
        data={"call_id": call_id, "status": status},
    ))


async def _handle_transcript(message: dict, call_id: str):
    """Push real-time transcript to SSE for dashboard."""
    transcript = message.get("transcript", "")
    role = message.get("role", "")
    # Some Vapi versions send it differently
    if not transcript:
        transcript = message.get("transcriptType", "")

    await store.push_event(SSEEvent(
        type=SSEEventType.TRANSCRIPT,
        data={
            "call_id": call_id,
            "role": role,
            "text": transcript,
        },
    ))


async def _handle_speech_update(message: dict, call_id: str):
    """Track who is speaking — useful for emotion analysis."""
    status = message.get("status", "")  # started / stopped
    role = message.get("role", "")  # assistant / user

    await store.push_event(SSEEvent(
        type=SSEEventType.TRANSCRIPT,
        data={
            "call_id": call_id,
            "speech_status": status,
            "role": role,
        },
    ))
