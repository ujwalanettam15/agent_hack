import os
from dotenv import load_dotenv

load_dotenv()

# Vapi
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
VAPI_PUBLIC_KEY = os.getenv("VAPI_PUBLIC_KEY", "")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID", "")

# Vapi Tool IDs (comma-separated in env, or set individually)
VAPI_TOOL_IDS = os.getenv("VAPI_TOOL_IDS", "").split(",") if os.getenv("VAPI_TOOL_IDS") else []

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Hume
HUME_API_KEY = os.getenv("HUME_API_KEY", "")
