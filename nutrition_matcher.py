# nutrition_matcher.py
"""
Спрощена версія без підвантаження локальної food‑бази.
Повертає тільки оцінку LLM, а всі DB‑поля — None / пусті.
"""

from typing import Dict, List, Any

def enhance_nutrition_estimate(
    llm_estimate: Dict[str, Any],
    food_items: List[str],
) -> Dict[str, Any]:
    """Повертає структуру, сумісну з попередньою, але без порівняння з БД."""
    return {
        "llm_estimate": llm_estimate,   # те, що витягнули з LLM
        "db_estimate": None,            # більше не використовуємо
        "food_matches": [],             # перелік збігів із БД тепер порожній
        "unmatched_items": food_items,  # просто повертаємо всі знайдені items
        "confidence_score": None,       # немає чим рахувати
    }
