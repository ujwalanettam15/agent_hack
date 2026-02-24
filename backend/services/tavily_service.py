import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Lazy import — tavily might not be installed yet
_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.TAVILY_API_KEY:
            logger.warning("TAVILY_API_KEY not set — search features disabled")
            return None
        from tavily import TavilyClient
        _client = TavilyClient(api_key=config.TAVILY_API_KEY)
    return _client


def search(query: str, max_results: int = 3) -> str:
    """Search the web via Tavily. Returns a concise single-line answer for Vapi."""
    client = _get_client()
    if not client:
        return f"Web search unavailable. Query was: {query}"

    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
            topic="general",
        )

        answer = response.get("answer", "")
        if not answer and response.get("results"):
            top = response["results"][0]
            answer = f"{top['title']}: {top['content'][:300]}"

        # Critical: no line breaks for Vapi tool responses
        return answer.replace("\n", " ").strip()

    except Exception as e:
        logger.error("Tavily search failed: %s", e)
        return f"Search failed: {str(e)}"


def research_for_task(company: str, action: str, service_type: str = "") -> dict:
    """Pre-call research. Returns context + sources for the task."""
    query_templates = {
        "cancel_service": f"{company} cancellation policy 2025 how to cancel",
        "negotiate_rate": f"{company} competitor rates {service_type} 2025 retention deals",
        "update_status": f"{company} account status check policy",
    }
    query = query_templates.get(action, f"{company} customer service tips 2025")

    client = _get_client()
    if not client:
        return {"context": "Research unavailable", "sources": []}

    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )
        return {
            "context": response.get("answer", "No summary available.").replace("\n", " "),
            "sources": [r["url"] for r in response.get("results", [])[:3]],
        }
    except Exception as e:
        logger.error("Tavily research failed: %s", e)
        return {"context": f"Research failed: {e}", "sources": []}
