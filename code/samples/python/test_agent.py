import asyncio
import os
import sys

from pathlib import Path
SRC_PATH = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_PATH))

from common.constants import OLLAMA_BASE_URL, OLLAMA_API_KEY, OLLAMA_MODEL
os.environ["AGENT_MODEL"] = OLLAMA_MODEL

from google.adk.agents.invocation_context import InvocationContext
from roles.shopping_agent.agent import root_agent

async def main():
    ctx = InvocationContext(agent=root_agent)
    ctx.append_user_message("I want to buy shoes")
    
    try:
        async for event in root_agent.run_async(ctx):
            if hasattr(event, "content") and event.content:
                print("AGENT:", event.content.text)
            elif event.error_message:
                print("ERROR:", event.error_message)
            else:
                print("EVENT:", event.author, getattr(event, "actions", ""))
    except Exception as e:
        print("EXCEPTION:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
