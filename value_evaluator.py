"""
Value Evaluation Logic for Overlanding Deals
Scores vehicles based on price, condition, capability, and market value.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from vehicle_database import get_vehicle_profile, calculate_platform_score


@dataclass
class VehicleListing:
    """Represents a vehicle listing found online"""
    url: str
    title: str
    make: str
    model: str
    year: int
    price: int
    mileage: int
    location: str
    description: str
    damage_type: Optional[str] = None
    title_status: Optional[str] = None
    features: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = []


@dataclass
class DealEvaluation:
    """Evaluation results for a vehicle listing"""
    listing: VehicleListing
    value_score: float  # 0-100, higher is better deal
    market_value_estimate: int
    discount_percent: float
    platform_score: float
    pros: List[str]
    cons: List[str]
    red_flags: List[str]
    recommended_action: str  # "STRONG BUY", "GOOD DEAL", "FAIR", "PASS", "RED FLAG"
    analysis: str
    estimated_upgrade_costs: Dict[str, int]


class ValueEvaluator:
    """Evaluates vehicle listings for value and overlanding suitability"""
    
    def __init__(self, max_budget: int = 10000):
        self.max_budget = max_budget
    
    def evaluate_listing(self, listing: VehicleListing) -> DealEvaluation:
        """Comprehensive evaluation of a vehicle listing"""
        
        # Get vehicle profile from database
        profile = get_vehicle_profile(listing.make, listing.model, listing.year)
        
        if not profile:
            return self._create_unknown_vehicle_evaluation(listing)
        
        # Calculate scores
        platform_score = calculate_platform_score(profile)
        market_value = self._estimate_market_value(listing, profile)
        discount_percent = ((market_value - listing.price) / market_value * 100) if market_value > 0 else 0
        
        # Analyze condition and issues
        pros, cons, red_flags = self._analyze_listing(listing, profile)
        
        # Calculate overall value score
        value_score = self._calculate_value_score(
            listing, profile, market_value, discount_percent, red_flags
        )
        
        # Determine recommendation
        recommended_action = self._determine_recommendation(value_score, discount_percent, red_flags, listing.price)
        
        # Generate analysis
        analysis = self._generate_analysis(listing, profile, market_value, discount_percent, value_score)
        
        # Estimate upgrade costs
        upgrade_costs = self._estimate_upgrade_costs(listing, profile)
        
        return DealEvaluation(
            listing=listing,
            value_score=value_score,
            market_value_estimate=market_value,
            discount_percent=discount_percent,
            platform_score=platform_score,
            pros=pros,
            cons=cons,
            red_flags=red_flags,
            recommended_action=recommended_action,
            analysis=analysis,
            estimated_upgrade_costs=upgrade_costs
        )
    
    def _estimate_market_value(self, listing: VehicleListing, profile) -> int:
        """Estimate market value based on year, mileage, and condition"""
        base_min, base_max = profile.typical_price_range
        
        # Adjust for year within range
        year_factor = (listing.year - profile.year_range[0]) / (profile.year_range[1] - profile.year_range[0])
        base_value = base_min + (base_max - base_min) * year_factor
        
        # Adjust for mileage (roughly $0.05 per mile reduction)
        mileage_reduction = (listing.mileage / 10000) * 500
        estimated_value = base_value - mileage_reduction
        
        # Adjust for damage
        if listing.damage_type:
            damage_lower = listing.damage_type.lower()
            if "hail" in damage_lower:
                estimated_value *= 0.85  # 15% reduction for hail
            elif "cosmetic" in damage_lower or "minor" in damage_lower:
                estimated_value *= 0.90  # 10% reduction
            elif "side" in damage_lower or "rear" in damage_lower:
                estimated_value *= 0.85  # 15% reduction
            elif "front" in damage_lower:
                estimated_value *= 0.75  # 25% reduction
        
        # Adjust for title status
        if listing.title_status:
            title_lower = listing.title_status.lower()
            if "salvage" in title_lower or "rebuilt" in title_lower:
                estimated_value *= 0.70  # 30% reduction for salvage
        
        return max(int(estimated_value), 1000)  # Minimum $1k estimate
    
    def _analyze_listing(self, listing: VehicleListing, profile) -> Tuple[List[str], List[str], List[str]]:
        """Analyze listing for pros, cons, and red flags"""
        pros = []
        cons = []
        red_flags = []
        
        # Check price
        if listing.price <= self.max_budget:
            pros.append(f"Within budget at ${listing.price:,}")
        else:
            cons.append(f"Over budget: ${listing.price:,} > ${self.max_budget:,}")
        
        # Check platform quality
        if profile.reliability_score >= 8:
            pros.append(f"Excellent reliability ({profile.reliability_score}/10)")
        elif profile.reliability_score >= 7:
            pros.append(f"Good reliability ({profile.reliability_score}/10)")
        else:
            cons.append(f"Average reliability ({profile.reliability_score}/10)")
        
        if profile.overlanding_capability >= 8:
            pros.append(f"Excellent overlanding capability ({profile.overlanding_capability}/10)")
        elif profile.overlanding_capability >= 7:
            pros.append(f"Good overlanding capability ({profile.overlanding_capability}/10)")
        
        if profile.upgrade_potential >= 8:
            pros.append(f"Great upgrade potential ({profile.upgrade_potential}/10)")
        
        # Check mileage
        if listing.mileage < 100000:
            pros.append(f"Lower mileage: {listing.mileage:,} miles")
        elif listing.mileage < 150000:
            pros.append(f"Reasonable mileage: {listing.mileage:,} miles")
        elif listing.mileage < 200000:
            cons.append(f"Higher mileage: {listing.mileage:,} miles")
        else:
            cons.append(f"Very high mileage: {listing.mileage:,} miles")
            red_flags.append("Extremely high mileage - verify maintenance records")
        
        # Check for known issues in description
        desc_lower = listing.description.lower()
        
        for issue in profile.common_issues:
            if any(keyword in desc_lower for keyword in issue.lower().split()):
                cons.append(f"Known issue mentioned: {issue}")
        
        for red_flag_item in profile.red_flags:
            if any(keyword in desc_lower for keyword in red_flag_item.lower().split()):
                red_flags.append(f"RED FLAG: {red_flag_item}")
        
        # Check title status
        if listing.title_status:
            title_lower = listing.title_status.lower()
            if any(bad in title_lower for bad in ["export only", "cannot be registered", "non-repairable", "parts only"]):
                red_flags.append(f"⛔ CANNOT REGISTER IN COLORADO: {listing.title_status}")
            elif "salvage" in title_lower and "rebuilt" not in title_lower:
                cons.append(f"Salvage title (can be rebuilt)")
            elif "rebuilt" in title_lower:
                cons.append(f"Rebuilt title (verify quality)")
            elif "clean" in title_lower:
                pros.append("Clean title")
        
        # Check damage type  
        if listing.damage_type:
            damage_lower = listing.damage_type.lower()
            if any(bad in damage_lower for bad in ["rollover", "undercarriage", "flood", "fire"]):
                red_flags.append(f"⛔ SEVERE DAMAGE TYPE: {listing.damage_type}")
            elif any(ok in damage_lower for ok in ["hail", "vandalism", "cosmetic"]):
                pros.append(f"Acceptable damage type: {listing.damage_type}")
            elif "minor" in damage_lower:
                pros.append(f"Minor damage: {listing.damage_type}")
            else:
                cons.append(f"Damage: {listing.damage_type} - needs inspection")
        
        return pros, cons, red_flags
    
    def _calculate_value_score(
        self, listing: VehicleListing, profile, market_value: int, 
        discount_percent: float, red_flags: List[str]
    ) -> float:
        """Calculate overall value score (0-100)"""
        
        # Start with discount percentage (0-40 points)
        discount_score = min(discount_percent, 40)
        
        # Platform quality (0-30 points)
        platform_quality = calculate_platform_score(profile)
        platform_points = (platform_quality / 10) * 30
        
        # Price to budget ratio (0-20 points)
        budget_ratio = listing.price / self.max_budget
        if budget_ratio <= 0.7:
            budget_points = 20
        elif budget_ratio <= 0.9:
            budget_points = 15
        elif budget_ratio <= 1.0:
            budget_points = 10
        else:
            budget_points = 0
        
        # Mileage factor (0-10 points)
        if listing.mileage < 100000:
            mileage_points = 10
        elif listing.mileage < 150000:
            mileage_points = 7
        elif listing.mileage < 200000:
            mileage_points = 4
        else:
            mileage_points = 0
        
        total_score = discount_score + platform_points + budget_points + mileage_points
        
        # Penalties
        for red_flag in red_flags:
            total_score -= 30  # Heavy penalty for red flags
        
        return max(0, min(100, total_score))
    
    def _determine_recommendation(
        self, value_score: float, discount_percent: float, 
        red_flags: List[str], price: int
    ) -> str:
        """Determine buy recommendation"""
        
        if red_flags:
            return "🚫 RED FLAG - PASS"
        
        if price > self.max_budget:
            return "💰 OVER BUDGET - PASS"
        
        if value_score >= 80:
            return "🔥 STRONG BUY - ACT FAST"
        elif value_score >= 65:
            return "✅ GOOD DEAL - INVESTIGATE"
        elif value_score >= 50:
            return "⚖️ FAIR - CONSIDER IF INSPECTED"
        else:
            return "👎 PASS - WEAK VALUE"
    
    def _generate_analysis(
        self, listing: VehicleListing, profile, market_value: int,
        discount_percent: float, value_score: float
    ) -> str:
        """Generate human-readable analysis"""
        
        analysis_parts = []
        
        # Value summary
        analysis_parts.append(
            f"**Value Analysis:** Listed at ${listing.price:,} vs estimated market value of "
            f"${market_value:,} = {discount_percent:.1f}% discount. Value score: {value_score:.1f}/100."
        )
        
        # Platform analysis
        analysis_parts.append(
            f"\n**Platform:** {profile.make} {profile.model} is rated {profile.reliability_score}/10 for reliability, "
            f"{profile.overlanding_capability}/10 for overlanding, and {profile.upgrade_potential}/10 for upgrades."
        )
        
        # Key features
        if profile.key_features:
            features = ", ".join(profile.key_features[:3])
            analysis_parts.append(f"\n**Key Features:** {features}")
        
        # Notes from database
        if profile.notes:
            analysis_parts.append(f"\n**Platform Notes:** {profile.notes}")
        
        return "".join(analysis_parts)
    
    def _estimate_upgrade_costs(self, listing: VehicleListing, profile) -> Dict[str, int]:
        """Estimate costs for common overlanding upgrades"""
        
        upgrades = {
            "All-Terrain Tires": 1200,
            "Basic Lift (2-3\")": 800,
            "Rock Sliders": 600,
            "Skid Plates": 400,
            "Roof Rack/Platform": 800,
            "Recovery Gear": 300,
            "LED Lighting": 400,
            "Dual Battery System": 600,
            "RTT (Rooftop Tent)": 1500,
        }
        
        # Adjust based on vehicle size/platform
        if "Wrangler" in profile.model:
            # Wrangler has affordable aftermarket
            upgrades = {k: int(v * 0.9) for k, v in upgrades.items()}
        elif "4Runner" in profile.model or "Land Cruiser" in profile.model:
            # Toyota tax
            upgrades = {k: int(v * 1.1) for k, v in upgrades.items()}
        
        return upgrades
    
    def _create_unknown_vehicle_evaluation(self, listing: VehicleListing) -> DealEvaluation:
        """Create evaluation for unknown/unsupported vehicle"""
        return DealEvaluation(
            listing=listing,
            value_score=0,
            market_value_estimate=0,
            discount_percent=0,
            platform_score=0,
            pros=[],
            cons=["Vehicle not in supported platforms list"],
            red_flags=["Unknown platform - cannot evaluate"],
            recommended_action="❓ UNKNOWN PLATFORM - RESEARCH REQUIRED",
            analysis="This vehicle is not in our overlanding platform database. Manual research required.",
            estimated_upgrade_costs={}
        )
