import re

def validate_card_number(card_number: str) -> bool:
    """Validate card number using Luhn algorithm"""
    card_number = card_number.replace(" ", "")
    if not card_number.isdigit():
        return False
    
    if len(card_number) < 13 or len(card_number) > 19:
        return False
    
    # Luhn algorithm
    total = 0
    reverse_digits = card_number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    
    return total % 10 == 0

def validate_phone_number(phone: str) -> bool:
    """Validate phone number"""
    # Russian phone number pattern
    pattern = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    return bool(re.match(pattern, phone))

def validate_amount(amount: str, min_val: float = 0, max_val: float = 1000000) -> bool:
    """Validate amount"""
    try:
        value = float(amount)
        return min_val <= value <= max_val
    except ValueError:
        return False