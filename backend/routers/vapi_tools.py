"""
Vapi Tool Call Handler
POST /api/vapi/tool-call

Vapi sends tool-calls here when the voice agent invokes any of the 5 tools.
We route by function name, execute, and return results.

CRITICAL FORMAT (from Vapi docs):
- Request: message.toolCallList[].{id, name, arguments}
- Response: {"results": [{"name": "x", "toolCallId": "y", "result": "single-line string"}]}
- Always return HTTP 200
- result and error must be single-line strings
"""

import json
import logging

from fastapi import APIRouter, Request

from models.schemas import SSEEvent, SSEEventType
from services.task_store import store
from services import tavily_service
from services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/vapi/tool-call")
async def handle_tool_call(request: Request):
    body = await request.json()
    message = body.get("message", {})
    tool_call_list = message.get("toolCallList", [])
    call_obj = message.get("call", {})
    call_id = call_obj.get("id", "unknown")

    results = []

    for tool_call in tool_call_list:
        tc_id = tool_call.get("id", "")
        tc_name = tool_call.get("name", "")
        # Arguments come as an object (dict), not a JSON string
        args = tool_call.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        logger.info("Tool call: %s (id=%s) args=%s", tc_name, tc_id, args)

        try:
            result = await _dispatch_tool(tc_name, args, call_id)
        except Exception as e:
            logger.error("Tool %s failed: %s", tc_name, e)
            result = f"Error: {str(e)}"

        # Ensure single-line string
        result_str = str(result).replace("\n", " ").replace("\r", "")

        results.append({
            "name": tc_name,
            "toolCallId": tc_id,
            "result": result_str,
        })

    return {"results": results}


async def _dispatch_tool(name: str, args: dict, call_id: str) -> str:
    """Route tool call to the correct handler."""

    if name == "search_task_context":
        return await _handle_search_task_context(args, call_id)
    elif name == "tavily_search":
        return await _handle_tavily_search(args)
    elif name == "extract_entities":
        return await _handle_extract_entities(args, call_id)
    elif name == "update_neo4j":
        return await _handle_update_neo4j(args, call_id)
    elif name == "end_task":
        return await _handle_end_task(args, call_id)
    else:
        return f"Unknown tool: {name}"


# ── Tool Handlers ────────────────────────────────────────────


async def _handle_search_task_context(args: dict, call_id: str) -> str:
    """Return task details so the agent knows what to do."""
    task_id = args.get("task_id", "")

    # Try to find by exact ID first
    task = store.get_task(task_id)

    # If not found, find the first task that's currently calling
    if not task:
        for t in store.list_tasks():
            if t.call_id == call_id or t.status == "calling":
                task = t
                break

    # Last resort: return first pending task
    if not task:
        tasks = store.list_tasks()
        task = tasks[0] if tasks else None

    if not task:
        return "No task found. Ask the customer how you can help them."

    # Link call to task
    store.update_task(task.id, call_id=call_id)

    context = (
        f"Task: {task.action.value} for {task.company}. "
        f"Client: {task.user_name}. "
    )
    if task.current_rate:
        context += f"Current rate: ${task.current_rate}/month. "
    if task.target_rate:
        context += f"Target rate: ${task.target_rate}/month. "
    if task.notes:
        context += f"Notes: {task.notes} "
    if task.research_context:
        context += f"Research: {task.research_context} "

    return context


async def _handle_tavily_search(args: dict) -> str:
    """Web search via Tavily."""
    query = args.get("query", "")
    if not query:
        return "No search query provided."
    return tavily_service.search(query)


async def _handle_extract_entities(args: dict, call_id: str) -> str:
    """Extract and log entities from the conversation."""
    entity_type = args.get("entity_type", "other")
    value = args.get("value", "")
    context = args.get("context", "")

    if not value:
        return "No value provided to extract."

    # Store in Neo4j
    neo4j_service.add_entity(entity_type, value, context, call_id)

    # Find the task linked to this call and update it
    for task in store.list_tasks():
        if task.call_id == call_id:
            if entity_type == "confirmation_number":
                store.update_task(task.id, confirmation_number=value)
            elif entity_type == "price":
                store.update_task(task.id, outcome=f"New rate: {value}")
            break

    # Push to SSE for dashboard
    await store.push_event(SSEEvent(
        type=SSEEventType.ENTITY_EXTRACTED,
        data={
            "entity_type": entity_type,
            "value": value,
            "context": context,
            "call_id": call_id,
        },
    ))

    return f"Logged {entity_type}: {value}"


async def _handle_update_neo4j(args: dict, call_id: str) -> str:
    """Update the knowledge graph."""
    action = args.get("action", "")
    service_name = args.get("service_name", "")
    details_raw = args.get("details", "{}")

    try:
        details = json.loads(details_raw) if isinstance(details_raw, str) else details_raw
    except json.JSONDecodeError:
        details = {"raw": details_raw}

    if action == "cancel_service":
        result = neo4j_service.cancel_service(
            user_name="Neel",
            service_name=service_name,
            confirmation=details.get("confirmation", ""),
        )
    elif action == "negotiate_rate":
        result = neo4j_service.update_service_rate(
            service_name=service_name,
            old_rate=float(details.get("old_rate", 0)),
            new_rate=float(details.get("new_rate", 0)),
            confirmation=details.get("confirmation", ""),
        )
    elif action == "update_status":
        result = neo4j_service.update_status(service_name, str(details))
    else:
        result = neo4j_service.update_status(service_name, str(details))

    # Push graph update to SSE
    await store.push_event(SSEEvent(
        type=SSEEventType.GRAPH_UPDATED,
        data={"action": action, "service": service_name, "details": details},
    ))

    return f"Graph updated: {action} for {service_name}. {json.dumps(result)}"


async def _handle_end_task(args: dict, call_id: str) -> str:
    """Mark task complete and prepare for call end."""
    status = args.get("status", "completed")
    summary = args.get("summary", "")

    # Find and update the task
    for task in store.list_tasks():
        if task.call_id == call_id:
            new_status = {
                "completed": "completed",
                "failed": "failed",
                "needs_followup": "needs_followup",
                "transferred": "needs_followup",
            }.get(status, "completed")

            store.update_task(task.id, status=new_status, outcome=summary)
            await store.push_task_update(task)
            break

    return f"Task marked as {status}. {summary}"
