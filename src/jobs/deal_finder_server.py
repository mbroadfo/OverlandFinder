"""Overland Finder Agent - HTTP Server Mode
Runs the agent as a REST API server for production use.
"""

import os
import argparse
import asyncio
from uuid import uuid4
from dotenv import load_dotenv

from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from agent_framework import (
    WorkflowBuilder,
    WorkflowContext,
    AgentRunUpdateEvent,
    AgentRunResponseUpdate,
    TextContent,
    Role,
    ChatMessage,
    handler,
)
from azure.ai.agentserver.agentframework import from_agent_framework

from src.evaluator.value_evaluator import ValueEvaluator
from src.evaluator.deal_finder_agent import DealFinderTools

# Load environment variables
load_dotenv(override=True)


class DealFinderWorkflowExecutor:
    """Workflow executor for Deal Finder system"""
    
    def __init__(self):
        self.id = "deal-finder-executor"
        self.tools = DealFinderTools()
        self.agent = None
    
    async def initialize(self):
        """Initialize the AI agent"""
        project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        model_deployment = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME")
        
        if not project_endpoint or "<" in project_endpoint:
            raise ValueError("Please set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT_NAME in .env")
        
        credential = DefaultAzureCredential()
        client = AzureAIClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment,
            credential=credential,
        )
        
        self.agent = await client.create_agent(  # type: ignore[misc]
            name="OverlandingDealFinder",
            instructions="""You are an expert overlanding vehicle deal finder and evaluator. 

Your mission is to help find incredible VALUE on capable overlanding vehicles - primarily Jeep Wranglers, 
Toyota 4Runners/Tacomas/Land Cruisers, Lexus GX/LX, Nissan Xterras/Frontiers, and similar platforms.

The user's budget is about $10k for purchase with $5k remaining for upgrades.

PRIORITIES (in order):
1. **Value** - Find deals significantly below market value
2. **Capability** - Ensure vehicle is suitable for overlanding in Colorado/Wyoming/Utah/Montana/Idaho
3. **Reliability** - Prefer mechanically sound platforms
4. **Upgrade Potential** - Look for platforms with good aftermarket support

ACCEPTABLE:
- Cosmetic damage (hail, dents, ugly paint)
- Higher mileage if well-maintained
- Older vehicles on reliable platforms
- Salvage/rebuilt titles IF registerable in Colorado

RED FLAGS (AUTO-REJECT):
- "Export Only" or "Cannot be registered in CO" titles
- Rollover, undercarriage, flood, or fire damage
- Known serious mechanical issues without fix
- Over budget without exceptional value

When evaluating deals, be thorough and analytical. Consider:
- Market value vs asking price
- Platform reliability and capability
- Common issues for that model/year
- Upgrade costs and potential
- Colorado registration eligibility""",
            tools=[
                self.tools.get_target_vehicles,
                self.tools.get_vehicle_knowledge,
                self.tools.decode_vin,
                self.tools.evaluate_deal,
                self.tools.get_saved_deals,
            ],
        )
    
    @handler  # type: ignore[arg-type]
    async def handle_messages(self, messages: list[ChatMessage], ctx: WorkflowContext) -> None:
        """Handle incoming messages and generate responses"""
        
        # Initialize agent if needed
        if not self.agent:
            await self.initialize()
        
        # Run agent
        response = await self.agent.run(messages)
        
        # Return responses
        for message in response.messages:
            if message.role == Role.ASSISTANT:
                await ctx.add_event(
                    AgentRunUpdateEvent(
                        self.id,
                        data=AgentRunResponseUpdate(
                            contents=[TextContent(text=message.contents[-1].text)],
                            role=Role.ASSISTANT,
                            response_id=str(uuid4()),
                        ),
                    )
                )


async def run_server_async(port: int = 8087):
    """Run the agent as an HTTP server"""
    print(f"🚙 Starting Overland Finder Agent Server on port {port}...")
    
    # Initialize executor and agent
    executor = DealFinderWorkflowExecutor()
    await executor.initialize()
    
    # Run agent as server
    await from_agent_framework(executor.agent, port=port).run_async()  # type: ignore[call-overload]


def run_server(port: int = 8087):
    """Synchronous wrapper for running server"""
    asyncio.run(run_server_async(port))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Overland Finder Agent Server")
    parser.add_argument("--server", action="store_true", help="Run in server mode")
    parser.add_argument("--port", type=int, default=8087, help="Server port (default: 8087)")
    
    args = parser.parse_args()
    
    if args.server:
        run_server(args.port)
    else:
        print("Usage: python deal_finder_server.py --server [--port 8087]")
        print("\nRun as HTTP server for production use and AI Toolkit Agent Inspector integration.")
