"""
VIN Decoder - NHTSA vPIC API Integration
Based on VehicleWellnessCenter implementation

Uses free NHTSA (National Highway Traffic Safety Administration) API to:
- Validate VIN format per ISO 3779 standard
- Decode VIN to get comprehensive vehicle specifications
- Extract make, model, year, engine, transmission, body type, etc.
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
import requests


# ============================================================================
# VIN Validation Constants (ISO 3779)
# ============================================================================

VIN_TRANSLITERATION = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
    '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
}

VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# Invalid characters in VIN (ISO 3779)
INVALID_VIN_CHARS = re.compile(r'[IOQioq]')


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class VehicleSpecs:
    """Vehicle specifications from VIN decode"""
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    
    # Engine
    engine_cylinders: Optional[int] = None
    engine_displacement: Optional[float] = None  # Liters
    engine_fuel_type: Optional[str] = None
    engine_horsepower: Optional[int] = None
    
    # Body
    body_type: Optional[str] = None
    body_doors: Optional[int] = None
    
    # Transmission
    transmission_type: Optional[str] = None
    transmission_speeds: Optional[int] = None
    
    # Other
    drive_type: Optional[str] = None
    gvwr: Optional[int] = None  # Gross Vehicle Weight Rating
    
    # Metadata
    source: str = "NHTSA_vPIC"
    raw_data: Optional[Dict[str, Any]] = None


# ============================================================================
# VIN Validation Functions
# ============================================================================

def sanitize_vin(vin: str) -> str:
    """
    Sanitize VIN input (remove spaces, hyphens, convert to uppercase)
    
    Args:
        vin: Raw VIN input
        
    Returns:
        Sanitized VIN
    """
    return re.sub(r'[\s-]', '', vin).upper().strip()


def calculate_check_digit(vin: str) -> str:
    """
    Calculate VIN check digit per ISO 3779
    
    Algorithm:
    1. Transliterate each character to its numeric value
    2. Multiply by position weight factor
    3. Sum all products
    4. Take modulo 11
    5. If 10, check digit is 'X', otherwise the digit itself
    
    Args:
        vin: 17-character VIN (uppercase)
        
    Returns:
        Check digit ('0'-'9' or 'X')
    """
    total = 0
    
    for i in range(17):
        char = vin[i]
        value = VIN_TRANSLITERATION.get(char)
        
        if value is None:
            return ''
        
        total += value * VIN_WEIGHTS[i]
    
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)


def is_valid_vin(vin: str) -> bool:
    """
    Validate VIN format and check digit
    
    Implements ISO 3779 standard:
    - 17 characters (alphanumeric, excluding I, O, Q)
    - Position 9 is check digit (0-9 or X)
    - Check digit calculated using weighted sum modulo 11
    
    Args:
        vin: Vehicle Identification Number
        
    Returns:
        True if valid, False otherwise
    """
    # Normalize to uppercase
    normalized = vin.upper().strip()
    
    # Check length
    if len(normalized) != 17:
        return False
    
    # Check for invalid characters (I, O, Q)
    if INVALID_VIN_CHARS.search(normalized):
        return False
    
    # Calculate check digit
    calculated = calculate_check_digit(normalized)
    actual = normalized[8]  # Position 9 (0-indexed)
    
    return calculated == actual


def get_vin_validation_error(vin: str) -> Optional[str]:
    """
    Validate and return error message if invalid
    
    Args:
        vin: Vehicle Identification Number
        
    Returns:
        None if valid, error message if invalid
    """
    sanitized = sanitize_vin(vin)
    
    if not sanitized:
        return 'VIN is required'
    
    if len(sanitized) != 17:
        return f'VIN must be exactly 17 characters (got {len(sanitized)})'
    
    if INVALID_VIN_CHARS.search(sanitized):
        return 'VIN cannot contain the letters I, O, or Q'
    
    if not is_valid_vin(sanitized):
        return 'Invalid VIN check digit'
    
    return None


# ============================================================================
# NHTSA vPIC API Integration
# ============================================================================

def decode_vin(vin: str) -> Optional[VehicleSpecs]:
    """
    Decode VIN using NHTSA vPIC API
    
    Free government API provides 145+ vehicle data points including:
    - Make, model, year, trim
    - Engine specs (cylinders, displacement, fuel type, horsepower)
    - Body type and doors
    - Transmission type and speeds
    - Drive type (4WD, AWD, FWD, RWD)
    - GVWR and other specs
    
    Args:
        vin: 17-character Vehicle Identification Number
        
    Returns:
        VehicleSpecs object or None if decode failed
        
    Raises:
        ValueError: If VIN is invalid
        requests.RequestException: If API call fails
    """
    # Sanitize and validate
    sanitized = sanitize_vin(vin)
    error = get_vin_validation_error(sanitized)
    
    if error:
        raise ValueError(error)
    
    # Call NHTSA vPIC API
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{sanitized}?format=json"
    
    print(f"[VIN Decode] Fetching specs for VIN: {sanitized}")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    
    if not data.get('Results') or len(data['Results']) == 0:
        raise ValueError('No results returned from NHTSA API')
    
    result = data['Results'][0]
    
    # Check for API errors
    if result.get('ErrorCode') and result['ErrorCode'] != '0':
        error_text = result.get('ErrorText', 'Unknown error')
        raise ValueError(f'NHTSA API error: {error_text}')
    
    # Map response to VehicleSpecs
    return map_nhtsa_response(result)


def map_nhtsa_response(result: Dict[str, Any]) -> VehicleSpecs:
    """
    Map NHTSA vPIC response to VehicleSpecs format
    
    Args:
        result: NHTSA API response dictionary
        
    Returns:
        VehicleSpecs object
    """
    def safe_int(value: Any) -> Optional[int]:
        """Safely convert to int or return None"""
        if not value or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def safe_float(value: Any) -> Optional[float]:
        """Safely convert to float or return None"""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    specs = VehicleSpecs(
        # Core identification
        year=safe_int(result.get('ModelYear')) or 0,
        make=result.get('Make') or 'Unknown',
        model=result.get('Model') or 'Unknown',
        trim=result.get('Trim') if result.get('Trim') else None,
        
        # Engine
        engine_cylinders=safe_int(result.get('EngineCylinders')),
        engine_displacement=safe_float(result.get('DisplacementL')),
        engine_fuel_type=result.get('FuelTypePrimary'),
        engine_horsepower=safe_int(result.get('EngineHP')),
        
        # Body
        body_type=result.get('BodyClass'),
        body_doors=safe_int(result.get('Doors')),
        
        # Transmission
        transmission_type=result.get('TransmissionStyle'),
        transmission_speeds=safe_int(result.get('TransmissionSpeeds')),
        
        # Other
        drive_type=result.get('DriveType'),
        gvwr=safe_int(result.get('GVWR')),
        
        # Metadata
        source="NHTSA_vPIC",
        raw_data=result
    )
    
    return specs


# ============================================================================
# Convenience Functions
# ============================================================================

def get_vehicle_info_from_vin(vin: str) -> str:
    """
    Get human-readable vehicle information from VIN
    
    Args:
        vin: Vehicle Identification Number
        
    Returns:
        Formatted string with vehicle details
    """
    try:
        specs = decode_vin(vin)
        
        if not specs:
            return "Unable to decode VIN"
        
        info = f"**{specs.year} {specs.make} {specs.model}**"
        
        if specs.trim:
            info += f" {specs.trim}"
        
        info += "\n\n**Engine:**\n"
        if specs.engine_cylinders:
            info += f"- {specs.engine_cylinders} cylinders"
        if specs.engine_displacement:
            info += f", {specs.engine_displacement}L"
        if specs.engine_fuel_type:
            info += f", {specs.engine_fuel_type}"
        if specs.engine_horsepower:
            info += f", {specs.engine_horsepower} HP"
        
        if specs.body_type:
            info += f"\n\n**Body:** {specs.body_type}"
            if specs.body_doors:
                info += f", {specs.body_doors} doors"
        
        if specs.transmission_type:
            info += f"\n\n**Transmission:** {specs.transmission_type}"
            if specs.transmission_speeds:
                info += f" ({specs.transmission_speeds}-speed)"
        
        if specs.drive_type:
            info += f"\n\n**Drive:** {specs.drive_type}"
        
        return info
        
    except ValueError as e:
        return f"VIN Decode Error: {str(e)}"
    except requests.RequestException as e:
        return f"API Error: {str(e)}"


# ============================================================================
# Testing / CLI
# ============================================================================

if __name__ == "__main__":
    # Test VINs
    test_vins = [
        "1C4PJMBS9HW664582",  # 2017 Jeep Cherokee
        "1FTFW1ET7BFA51376",  # Ford F-150
        "WBADT43452G935194",  # BMW 3 Series
    ]
    
    print("=== VIN Decoder Test ===\n")
    
    for vin in test_vins:
        print(f"\nVIN: {vin}")
        print("-" * 60)
        
        # Validation
        error = get_vin_validation_error(vin)
        if error:
            print(f"❌ INVALID: {error}")
            continue
        
        print("✅ Valid VIN")
        
        # Decode
        try:
            print(get_vehicle_info_from_vin(vin))
        except Exception as e:
            print(f"❌ Decode failed: {e}")
