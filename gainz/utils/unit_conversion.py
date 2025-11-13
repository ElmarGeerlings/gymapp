"""
Unit conversion utilities for weight measurements.
"""

from decimal import Decimal, ROUND_HALF_UP


def kg_to_lbs(kg_weight):
    """
    Convert weight from kilograms to pounds.
    
    Args:
        kg_weight (Decimal or float): Weight in kilograms
    
    Returns:
        Decimal: Weight in pounds, rounded to 2 decimal places
    """
    if kg_weight is None:
        return None
    
    # Convert to Decimal for precise calculation
    kg_decimal = Decimal(str(kg_weight))
    # 1 kg = 2.20462 lbs
    conversion_factor = Decimal('2.20462')
    lbs_weight = kg_decimal * conversion_factor
    
    # Round to 2 decimal places
    return lbs_weight.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def lbs_to_kg(lbs_weight):
    """
    Convert weight from pounds to kilograms.
    
    Args:
        lbs_weight (Decimal or float): Weight in pounds
    
    Returns:
        Decimal: Weight in kilograms, rounded to 2 decimal places
    """
    if lbs_weight is None:
        return None
    
    # Convert to Decimal for precise calculation
    lbs_decimal = Decimal(str(lbs_weight))
    # 1 lbs = 0.453592 kg
    conversion_factor = Decimal('0.453592')
    kg_weight = lbs_decimal * conversion_factor
    
    # Round to 2 decimal places
    return kg_weight.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def convert_weight(weight, from_unit, to_unit):
    """
    Convert weight from one unit to another.
    
    Args:
        weight (Decimal or float): Weight to convert
        from_unit (str): Source unit ('kg' or 'lbs')
        to_unit (str): Target unit ('kg' or 'lbs')
    
    Returns:
        Decimal: Converted weight, or original weight if units are the same
    
    Raises:
        ValueError: If invalid units are provided
    """
    if weight is None:
        return None
    
    valid_units = ['kg', 'lbs']
    if from_unit not in valid_units or to_unit not in valid_units:
        raise ValueError(f"Units must be one of {valid_units}")
    
    # No conversion needed if units are the same
    if from_unit == to_unit:
        return Decimal(str(weight))
    
    # Perform conversion
    if from_unit == 'kg' and to_unit == 'lbs':
        return kg_to_lbs(weight)
    elif from_unit == 'lbs' and to_unit == 'kg':
        return lbs_to_kg(weight)


def display_weight_with_unit(weight, unit):
    """
    Format weight for display with appropriate unit suffix.
    
    Args:
        weight (Decimal or float): Weight value
        unit (str): Unit ('kg' or 'lbs')
    
    Returns:
        str: Formatted weight string (e.g., "100.5 kg", "220.5 lbs")
    """
    if weight is None:
        return ""
    
    # Format weight to remove unnecessary decimal places
    weight_decimal = Decimal(str(weight))
    # Remove trailing zeros after decimal point
    formatted_weight = weight_decimal.normalize()
    
    return f"{formatted_weight} {unit}"