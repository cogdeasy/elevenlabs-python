"""ConvAI: create a conversational AI agent, fetch its config, then delete it.

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python examples/convai_agent.py [agent-name]

Set ELEVENLABS_BASE_URL to point the client at a non-production API
(used by the CI smoke tier to run against a local mock server).
"""

import os
import sys

from elevenlabs import ConversationalConfig
from elevenlabs.client import ElevenLabs


def main() -> None:
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "sdk-example-agent"

    client = ElevenLabs(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        base_url=os.environ.get("ELEVENLABS_BASE_URL"),
    )

    created = client.conversational_ai.agents.create(
        name=agent_name,
        conversation_config=ConversationalConfig(),
    )
    print(f"Created agent: {created.agent_id}")

    agent = client.conversational_ai.agents.get(created.agent_id)
    print(f"Fetched agent: {agent.agent_id} (name={agent.name})")

    client.conversational_ai.agents.delete(created.agent_id)
    print(f"Deleted agent: {created.agent_id}")


if __name__ == "__main__":
    main()
