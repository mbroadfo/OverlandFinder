"""
Overlanding Vehicle Knowledge Base
Contains market data, reliability ratings, and upgrade potential for target vehicles.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class VehicleProfile:
    """Profile for an overlanding-capable vehicle platform"""
    make: str
    model: str
    year_range: Tuple[int, int]
    typical_price_range: Tuple[int, int]  # (min, max) for reasonable condition
    reliability_score: int  # 1-10, 10 being most reliable
    overlanding_capability: int  # 1-10, 10 being best
    upgrade_potential: int  # 1-10, 10 being easiest/most options
    key_features: List[str]
    common_issues: List[str]
    red_flags: List[str]
    ideal_trim_levels: List[str]
    notes: str


# Overlanding Vehicle Database
VEHICLE_PROFILES: Dict[str, VehicleProfile] = {
    "Jeep Wrangler JK": VehicleProfile(
        make="Jeep",
        model="Wrangler",
        year_range=(2007, 2018),
        typical_price_range=(8000, 25000),
        reliability_score=7,
        overlanding_capability=9,
        upgrade_potential=10,
        key_features=["Solid axles", "Removable top/doors", "3.6L Pentastar (2012+)", "4WD", "Short wheelbase"],
        common_issues=["ABS module failure (2014-2018)", "Oil filter housing leaks", "Death wobble", "Soft top wear"],
        red_flags=["3.8L engine (2007-2011)", "Frame rust", "Poorly done lift kits", "Flood damage"],
        ideal_trim_levels=["Rubicon", "Willys Wheeler", "Sahara"],
        notes="Best all-around value. Huge aftermarket. 2012+ with 3.6L preferred. Watch for 2014-2018 ABS module issues (parts on backorder)."
    ),
    
    "Jeep Wrangler TJ": VehicleProfile(
        make="Jeep",
        model="Wrangler",
        year_range=(1997, 2006),
        typical_price_range=(5000, 15000),
        reliability_score=7,
        overlanding_capability=8,
        upgrade_potential=10,
        key_features=["Simple 4.0L I6", "Solid axles", "Coil suspension", "Removable top"],
        common_issues=["Rust (frames, tubs)", "Soft top condition", "4.0L head cracks (rare)"],
        red_flags=["Frame rust", "Rust in tub/rockers", "2.5L 4-cylinder engine"],
        ideal_trim_levels=["Rubicon", "Sport (with 4.0L)"],
        notes="Simpler, cheaper platform. Easier to work on. Watch carefully for rust on older models."
    ),
    
    "Toyota 4Runner 4th Gen": VehicleProfile(
        make="Toyota",
        model="4Runner",
        year_range=(2003, 2009),
        typical_price_range=(8000, 18000),
        reliability_score=9,
        overlanding_capability=8,
        upgrade_potential=8,
        key_features=["4.0L V6 or 4.7L V8", "Body-on-frame", "4WD", "Locking rear diff (some)"],
        common_issues=["Rust on frames (recall)", "Lower ball joints", "Timing belt (V8)"],
        red_flags=["Frame rust (check for recall completion)", "Pink milkshake (transmission cooler failure in V6)"],
        ideal_trim_levels=["SR5 4WD", "Sport Edition", "Limited 4WD"],
        notes="Legendary reliability. Check frame rust recall status. V6 preferred for fuel economy, V8 for power."
    ),
    
    "Toyota 4Runner 5th Gen": VehicleProfile(
        make="Toyota",
        model="4Runner",
        year_range=(2010, 2023),
        typical_price_range=(15000, 45000),
        reliability_score=9,
        overlanding_capability=9,
        upgrade_potential=8,
        key_features=["4.0L V6", "Body-on-frame", "KDSS (some)", "Crawl control", "Multi-terrain select"],
        common_issues=["Transmission shifting (minor)", "Carburetor-like fuel economy"],
        red_flags=["Accident damage", "Poor maintenance"],
        ideal_trim_levels=["Trail Edition", "TRD Off-Road", "TRD Pro"],
        notes="Peak reliability. Holds value extremely well. Hard to find undervalued. 2014+ has X-REAS."
    ),
    
    "Toyota Tacoma": VehicleProfile(
        make="Toyota",
        model="Tacoma",
        year_range=(2005, 2023),
        typical_price_range=(8000, 35000),
        reliability_score=9,
        overlanding_capability=8,
        upgrade_potential=9,
        key_features=["4.0L V6", "Proven drivetrain", "Manual available", "Excellent aftermarket"],
        common_issues=["Frame rust (2005-2010 recall)", "Leaf spring suspension", "Automatic transmission shifting"],
        red_flags=["Frame rust", "Salvage title from theft (common)", "Poorly modified"],
        ideal_trim_levels=["TRD Off-Road", "TRD Sport", "PreRunner (2WD but lift-able)"],
        notes="2nd & 3rd gen excellent. Check frame rust on 2005-2011. Manual transmission adds value."
    ),
    
    "Toyota Land Cruiser 100 Series": VehicleProfile(
        make="Toyota",
        model="Land Cruiser",
        year_range=(1998, 2007),
        typical_price_range=(8000, 20000),
        reliability_score=9,
        overlanding_capability=9,
        upgrade_potential=7,
        key_features=["4.7L V8", "Full-time 4WD", "Locking diffs", "Built-in overland capability"],
        common_issues=["AHC suspension failure", "Rust on older models", "Timing belt maintenance"],
        red_flags=["Deferred maintenance", "AHC not converted", "High miles without records"],
        ideal_trim_levels=["Any (all well-equipped)"],
        notes="Ultimate reliability. Complex active suspension often converted. High miles OK with maintenance."
    ),
    
    "Lexus GX470": VehicleProfile(
        make="Lexus",
        model="GX470",
        year_range=(2003, 2009),
        typical_price_range=(8000, 20000),
        reliability_score=9,
        overlanding_capability=8,
        upgrade_potential=7,
        key_features=["4.7L V8 (1UZ/2UZ)", "KDSS suspension", "Locking rear diff", "Luxury + capability"],
        common_issues=["Timing belt service", "Secondary air injection", "Rust on subframes"],
        red_flags=["No maintenance records", "Air suspension problems"],
        ideal_trim_levels=["Any (all similar)"],
        notes="Hidden gem. Land Cruiser Prado underneath. Cheaper than 4Runner. DIY-friendly."
    ),
    
    "Lexus GX460": VehicleProfile(
        make="Lexus",
        model="GX460",
        year_range=(2010, 2023),
        typical_price_range=(18000, 50000),
        reliability_score=9,
        overlanding_capability=8,
        upgrade_potential=7,
        key_features=["4.6L V8", "KDSS", "Crawl control", "Luxury comfort"],
        common_issues=["Timing belt service", "Complex electronics"],
        red_flags=["Accident damage", "Electrical issues"],
        ideal_trim_levels=["Premium", "Luxury"],
        notes="More modern GX platform. Excellent reliability. Usually priced high."
    ),
    
    "Nissan Xterra": VehicleProfile(
        make="Nissan",
        model="Xterra",
        year_range=(2005, 2015),
        typical_price_range=(4000, 12000),
        reliability_score=7,
        overlanding_capability=7,
        upgrade_potential=8,
        key_features=["4.0L V6", "Solid rear axle", "Manual available", "Simple platform"],
        common_issues=["Timing chain tensioners", "SMOD (transmission cooler)", "Rust"],
        red_flags=["SMOD (strawberry milkshake of death)", "Frame rust", "No maintenance records"],
        ideal_trim_levels=["Pro-4X", "Off-Road"],
        notes="Budget-friendly option. Address timing chain and SMOD early. Pro-4X is best trim."
    ),
    
    "Nissan Frontier": VehicleProfile(
        make="Nissan",
        model="Frontier",
        year_range=(2005, 2021),
        typical_price_range=(5000, 18000),
        reliability_score=7,
        overlanding_capability=7,
        upgrade_potential=8,
        key_features=["4.0L V6", "Solid rear axle", "Manual available", "Simple design"],
        common_issues=["Timing chain tensioners", "SMOD", "Dated interior"],
        red_flags=["SMOD", "Rust", "Poorly lifted"],
        ideal_trim_levels=["Pro-4X", "SV 4WD"],
        notes="Similar platform to Xterra. Budget option. Address SMOD and timing chain."
    ),
    
    "Ford Bronco (Classic)": VehicleProfile(
        make="Ford",
        model="Bronco",
        year_range=(1980, 1996),
        typical_price_range=(5000, 25000),
        reliability_score=6,
        overlanding_capability=8,
        upgrade_potential=9,
        key_features=["Simple V8", "Solid axles front/rear", "Removable top", "Classic style"],
        common_issues=["Rust everywhere", "Fuel economy", "Dated tech"],
        red_flags=["Rust in frame/body", "Engine swaps done poorly", "Electrical gremlins"],
        ideal_trim_levels=["XLT", "Eddie Bauer"],
        notes="Cool factor high. Watch for rust. Simple to work on. Fuel costs add up."
    ),
    
    "Chevy Colorado/ZR2": VehicleProfile(
        make="Chevrolet",
        model="Colorado",
        year_range=(2015, 2023),
        typical_price_range=(15000, 40000),
        reliability_score=7,
        overlanding_capability=8,
        upgrade_potential=7,
        key_features=["Diesel option", "ZR2 off-road trim", "Modern platform", "Good payload"],
        common_issues=["Diesel emissions issues", "Transmission concerns (some)"],
        red_flags=["Diesel with problems", "Accident damage", "Salvage title"],
        ideal_trim_levels=["ZR2", "Z71"],
        notes="Modern option. ZR2 is excellent but pricey. Diesel adds capability and complexity."
    ),
}


def get_vehicle_profile(make: str, model: str, year: int) -> Optional[VehicleProfile]:
    """Get vehicle profile for a specific make/model/year"""
    # Try to find exact match
    for key, profile in VEHICLE_PROFILES.items():
        if profile.make.lower() in make.lower() and profile.model.lower() in model.lower():
            if profile.year_range[0] <= year <= profile.year_range[1]:
                return profile
    return None


def calculate_platform_score(profile: VehicleProfile) -> float:
    """Calculate overall platform score for overlanding"""
    return (profile.reliability_score * 0.4 + 
            profile.overlanding_capability * 0.4 + 
            profile.upgrade_potential * 0.2)


def is_good_overlanding_platform(make: str, model: str, year: int) -> bool:
    """Quick check if vehicle is a good overlanding platform"""
    profile = get_vehicle_profile(make, model, year)
    if not profile:
        return False
    
    # Require minimum scores
    return (profile.reliability_score >= 6 and 
            profile.overlanding_capability >= 7)
