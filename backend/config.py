import os
from dotenv import load_dotenv

load_dotenv()

# Vapi
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
VAPI_PUBLIC_KEY = os.getenv("VAPI_PUBLIC_KEY", "")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "683ebace-9e80-430e-b1a4-4d41a635114a")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID", "")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Hume
HUME_API_KEY = os.getenv("HUME_API_KEY", "")
