"""Overland Finder Agent
AI-powered agent that finds and evaluates overlanding vehicle deals.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Annotated, Optional
from dotenv import load_dotenv

from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from agent_framework import WorkflowBuilder

from value_evaluator import ValueEvaluator, VehicleListing, DealEvaluation
from vehicle_database import VEHICLE_PROFILES, is_good_overlanding_platform
from vin_decoder import decode_vin, get_vehicle_info_from_vin, get_vin_validation_error

# Load environment variables
load_dotenv(override=True)


class DealFinderTools:
    """Tools for the Deal Finder Agent"""
    
    def __init__(self):
        self.max_budget = int(os.getenv("MAX_PURCHASE_PRICE", "10000"))
        self.evaluator = ValueEvaluator(max_budget=self.max_budget)
        self.database_file = os.getenv("DATABASE_FILE", "overlanding_deals.json")
        self.seen_listings_file = os.getenv("SEEN_LISTINGS_FILE", "seen_listings.txt")
        
    def get_target_vehicles(self) -> str:
        """Get list of target overlanding vehicles to search for."""
        target_vehicles = os.getenv("TARGET_VEHICLES", "").split(",")
        vehicle_list = [v.strip() for v in target_vehicles if v.strip()]
        
        result = "**Target Overlanding Vehicles:**\n\n"
        for vehicle in vehicle_list:
            result += f"- {vehicle}\n"
        
        result += f"\n**Search Parameters:**\n"
        result += f"- Max Purchase Price: ${self.max_budget:,}\n"
        result += f"- Year Range: {os.getenv('MIN_YEAR', '2000')}-{os.getenv('MAX_YEAR', '2020')}\n"
        result += f"- Max Mileage: {os.getenv('MAX_MILEAGE', '200000')} miles\n"
        result += f"- Location: {os.getenv('SEARCH_LOCATION', 'Denver, CO')}\n"
        
        return result
    
    def get_vehicle_knowledge(
        self, 
        vehicle_name: Annotated[str, "Vehicle make and model (e.g., 'Jeep Wrangler', 'Toyota 4Runner')"]
    ) -> str:
        """Get detailed knowledge about a specific overlanding vehicle platform."""
        
        # Find matching profile
        for key, profile in VEHICLE_PROFILES.items():
            if vehicle_name.lower() in key.lower():
                result = f"**{profile.make} {profile.model} ({profile.year_range[0]}-{profile.year_range[1]})**\n\n"
                result += f"**Ratings:**\n"
                result += f"- Reliability: {profile.reliability_score}/10\n"
                result += f"- Overlanding Capability: {profile.overlanding_capability}/10\n"
                result += f"- Upgrade Potential: {profile.upgrade_potential}/10\n\n"
                result += f"**Price Range:** ${profile.typical_price_range[0]:,} - ${profile.typical_price_range[1]:,}\n\n"
                result += f"**Key Features:** {', '.join(profile.key_features)}\n\n"
                result += f"**Common Issues:** {', '.join(profile.common_issues)}\n\n"
                result += f"**Red Flags:** {', '.join(profile.red_flags)}\n\n"
                result += f"**Ideal Trims:** {', '.join(profile.ideal_trim_levels)}\n\n"
                result += f"**Expert Notes:** {profile.notes}\n"
                
                return result
        
        return f"No detailed information found for '{vehicle_name}'. Try: Jeep Wrangler, Toyota 4Runner, Tacoma, Land Cruiser, Lexus GX470, Nissan Xterra"
    
    def decode_vin(
        self,
        vin: Annotated[str, "17-character Vehicle Identification Number to decode"]
    ) -> str:
        """
        Decode a VIN to get comprehensive vehicle specifications from NHTSA.
        
        Returns make, model, year, engine specs, transmission, body type, and more.
        Use this when a user provides a VIN or asks to verify vehicle details.
        """
        try:
            return get_vehicle_info_from_vin(vin)
        except Exception as e:
            return f"VIN Decode Error: {str(e)}"
    
    def evaluate_deal(
        self,
        url: Annotated[str, "URL of the listing"],
        title: Annotated[str, "Listing title"],
        make: Annotated[str, "Vehicle  make (e.g., 'Jeep', 'Toyota')"],
        model: Annotated[str, "Vehicle model (e.g., 'Wrangler', '4Runner')"],
        year: Annotated[int, "Year of vehicle"],
        price: Annotated[int, "Asking price in dollars"],
        mileage: Annotated[int, "Mileage on odometer"],
        location: Annotated[str, "Vehicle location"],
        description: Annotated[str, "Full description from listing"],
        damage_type: Annotated[Optional[str], "Type of damage if any (e.g., 'hail', 'minor rear end')"] = None,
        title_status: Annotated[Optional[str], "Title status (e.g., 'clean', 'salvage', 'rebuilt')"] = None,
    ) -> str:
        """Evaluate a specific vehicle listing for value and overlanding suitability."""
        
        # Create listing object
        listing = VehicleListing(
            url=url,
            title=title,
            make=make,
            model=model,
            year=year,
            price=price,
            mileage=mileage,
            location=location,
            description=description,
            damage_type=damage_type,
            title_status=title_status,
        )
        
        # Evaluate
        evaluation = self.evaluator.evaluate_listing(listing)
        
        # Format results
        result = f"# 🚙 {year} {make} {model} - Deal Evaluation\n\n"
        result += f"**Price:** ${price:,} | **Mileage:** {mileage:,} mi | **Location:** {location}\n\n"
        result += f"## {evaluation.recommended_action}\n\n"
        result += f"**Value Score:** {evaluation.value_score:.1f}/100\n"
        result += f"**Estimated Market Value:** ${evaluation.market_value_estimate:,}\n"
        result += f"**Discount:** {evaluation.discount_percent:.1f}%\n"
        result += f"**Platform Score:** {evaluation.platform_score:.1f}/10\n\n"
        
        if evaluation.red_flags:
            result += "### 🚨 RED FLAGS:\n"
            for flag in evaluation.red_flags:
                result += f"- {flag}\n"
            result += "\n"
        
        if evaluation.pros:
            result += "### ✅ PROS:\n"
            for pro in evaluation.pros:
                result += f"- {pro}\n"
            result += "\n"
        
        if evaluation.cons:
            result += "### ⚠️ CONS:\n"
            for con in evaluation.cons:
                result += f"- {con}\n"
            result += "\n"
        
        result += f"### 📊 Analysis:\n{evaluation.analysis}\n\n"
        
        if evaluation.estimated_upgrade_costs:
            result += "### 🔧 Estimated Upgrade Costs:\n"
            total_upgrade_cost = 0
            for upgrade, cost in list(evaluation.estimated_upgrade_costs.items())[:5]:
                result += f"- {upgrade}: ${cost:,}\n"
                total_upgrade_cost += cost
            result += f"\n**Sample 5 upgrades total:** ${total_upgrade_cost:,}\n"
            result += f"**Price + Upgrades:** ${price + total_upgrade_cost:,}\n\n"
        
        # Save if good deal
        if evaluation.value_score >= 50 and not evaluation.red_flags:
            self._save_deal(evaluation)
            result += f"✅ **Saved to database:** {self.database_file}\n"
        
        return result
    
    def _save_deal(self, evaluation: DealEvaluation):
        """Save a good deal to the database"""
        try:
            # Load existing deals
            if os.path.exists(self.database_file):
                with open(self.database_file, 'r') as f:
                    deals = json.load(f)
            else:
                deals = []
            
            # Add new deal
            deal_data = {
                "timestamp": datetime.now().isoformat(),
                "url": evaluation.listing.url,
                "vehicle": f"{evaluation.listing.year} {evaluation.listing.make} {evaluation.listing.model}",
                "price": evaluation.listing.price,
                "mileage": evaluation.listing.mileage,
                "location": evaluation.listing.location,
                "value_score": evaluation.value_score,
                "discount_percent": evaluation.discount_percent,
                "recommendation": evaluation.recommended_action,
            }
            
            deals.append(deal_data)
            
            # Save
            with open(self.database_file, 'w') as f:
                json.dump(deals, f, indent=2)
                
        except Exception as e:
            print(f"Error saving deal: {e}")
    
    def get_saved_deals(
        self,
        min_value_score: Annotated[int, "Minimum value score to filter (0-100)"] = 50
    ) -> str:
        """Get all saved deals from the database."""
        
        if not os.path.exists(self.database_file):
            return "No deals saved yet. Start searching!"
        
        try:
            with open(self.database_file, 'r') as f:
                deals = json.load(f)
            
            # Filter by score
            filtered_deals = [d for d in deals if d.get("value_score", 0) >= min_value_score]
            filtered_deals.sort(key=lambda x: x.get("value_score", 0), reverse=True)
            
            if not filtered_deals:
                return f"No deals found with value score >= {min_value_score}"
            
            result = f"# 💎 Saved Deals (Score >= {min_value_score})\n\n"
            result += f"Found {len(filtered_deals)} deals:\n\n"
            
            for i, deal in enumerate(filtered_deals[:10], 1):  # Top 10
                result += f"**{i}. {deal['vehicle']}**\n"
                result += f"   - Price: ${deal['price']:,} | Mileage: {deal['mileage']:,} mi\n"
                result += f"   - Value Score: {deal['value_score']:.1f} | Discount: {deal['discount_percent']:.1f}%\n"
                result += f"   - {deal['recommendation']}\n"
                result += f"   - Location: {deal['location']}\n"
                result += f"   - URL: {deal['url']}\n"
                result += f"   - Found: {deal['timestamp']}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error loading deals: {e}"


async def create_deal_finder_agent():
    """Create the Deal Finder AI agent"""
    
    # Get configuration
    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    model_deployment = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME")
    
    if not project_endpoint or "<" in project_endpoint:
        raise ValueError(
            "Please set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT_NAME in .env file.\n"
            "Get these from your Microsoft Foundry project."
        )
    
    # Create tools
    tools = DealFinderTools()
    
    # Create agent with tools
    async with DefaultAzureCredential() as credential:
        async with AzureAIClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment,
            credential=credential,
        ).create_agent(
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

When evaluating deals, be thorough and analytical like the ChatGPT advisor. Consider:
- Market value vs asking price
- Platform reliability and capability
- Common issues for that model/year
- Upgrade costs and potential
- Colorado registration eligibility

Use your tools to access vehicle knowledge and evaluate specific listings. Be honest about 
pros/cons and provide clear recommendations.""",
            tools=[
                tools.get_target_vehicles,
                tools.get_vehicle_knowledge,
                tools.decode_vin,
                tools.evaluate_deal,
                tools.get_saved_deals,
            ],
        ) as agent:
            return agent


async def main():
    """Main entry point"""
    print("🚙 Overland Finder Agent")
    print("=" * 60)
    
    try:
        agent = await create_deal_finder_agent()
        
        print("\nAgent ready! Try asking:")
        print("- 'What vehicles are you looking for?'")
        print("- 'Tell me about the Jeep Wrangler JK platform'")
        print("- 'Tell me about Toyota 4Runner'")
        print("- 'Evaluate this deal: [paste listing details]'")
        print("- 'Show me saved deals'")
        print("\nType 'quit' to exit\n")
        
        # Interactive loop
        while True:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Happy hunting!")
                break
            
            if not user_input:
                continue
            
            # Run agent
            print(f"\n🤖 Agent: ", end="", flush=True)
            async for chunk in agent.run_stream(user_input):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
            print("\n")
    
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease update your .env file with your Foundry project details.")
        print("Visit Microsoft Foundry to create a project and deploy a model.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
