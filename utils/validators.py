from datetime import datetime

def is_valid_vin(vin: str) -> bool:
    vin = vin.strip().upper()
    if len(vin) != 17:
        return False
    forbidden = {'I', 'O', 'Q'}
    if any(c in forbidden for c in vin):
        return False
    return vin.isalnum()

def parse_date(text: str) -> str | None:
    """Возвращает дату в формате YYYY-MM-DD или None"""
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None