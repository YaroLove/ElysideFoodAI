import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from fuzzywuzzy import fuzz
import re
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class NutritionMatcher:
    def __init__(self, db_path: str = 'food_db.json'):
        """Initialize the matcher with the food database."""
        logging.info("Loading food database...")
        with open(db_path, 'r') as f:
            self.food_db = json.load(f)
        logging.info(f"Loaded {len(self.food_db)} food items")
        
        # Pre-process food names for better matching
        self.food_names = [item['name'].lower() for item in self.food_db]
        
        # Common food variations and synonyms
        self.food_synonyms = {
            'bacon': ['bacon', 'pork bacon', 'turkey bacon', 'canadian bacon'],
            'bread': ['bread', 'white bread', 'wheat bread', 'whole grain bread'],
            'chicken': ['chicken', 'chicken breast', 'chicken thigh', 'chicken meat'],
            'beef': ['beef', 'ground beef', 'beef steak', 'beef meat'],
            'rice': ['rice', 'white rice', 'brown rice', 'cooked rice'],
            'potato': ['potato', 'potatoes', 'baked potato', 'mashed potato'],
            'egg': ['egg', 'eggs', 'chicken egg', 'boiled egg'],
            'pasta': ['pasta', 'spaghetti', 'noodles', 'macaroni'],
            'cheese': ['cheese', 'cheddar', 'mozzarella', 'american cheese'],
            'milk': ['milk', 'whole milk', 'skim milk', '2% milk'],
            'apple': ['apple', 'red apple', 'green apple', 'fresh apple'],
            'banana': ['banana', 'fresh banana', 'ripe banana'],
            'tomato': ['tomato', 'tomatoes', 'fresh tomato', 'raw tomato'],
            'lettuce': ['lettuce', 'iceberg lettuce', 'romaine lettuce', 'green lettuce'],
            'carrot': ['carrot', 'carrots', 'raw carrot', 'fresh carrot']
        }

    def preprocess_food_name(self, food_name: str) -> str:
        """Preprocess food name for better matching."""
        # Convert to lowercase
        name = food_name.lower()
        
        # Remove common words that don't affect meaning
        stop_words = ['fresh', 'raw', 'cooked', 'prepared', 'unprepared', 'frozen', 'canned']
        for word in stop_words:
            name = name.replace(word, '').strip()
        
        # Remove parentheses and their contents
        name = re.sub(r'\([^)]*\)', '', name).strip()
        
        # Remove multiple spaces
        name = ' '.join(name.split())
        
        return name

    def extract_quantity(self, food_item: str) -> Tuple[str, Optional[float], Optional[str]]:
        """Extract quantity and unit from a food item description."""
        # Common units and their variations
        units = {
            'g': ['g', 'gram', 'grams'],
            'ml': ['ml', 'milliliter', 'milliliters'],
            'cup': ['cup', 'cups'],
            'tbsp': ['tbsp', 'tablespoon', 'tablespoons'],
            'tsp': ['tsp', 'teaspoon', 'teaspoons'],
            'oz': ['oz', 'ounce', 'ounces'],
            'slice': ['slice', 'slices'],
            'piece': ['piece', 'pieces'],
            'large': ['large'],
            'medium': ['medium'],
            'small': ['small']
        }
        
        # Regular expression to match numbers (including decimals) followed by units
        quantity_pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)'
        match = re.search(quantity_pattern, food_item)
        
        if match:
            amount = float(match.group(1))
            unit = match.group(2).lower()
            
            # Standardize the unit
            for std_unit, variations in units.items():
                if unit in variations:
                    unit = std_unit
                    break
            
            # Remove the quantity and unit from the food item name
            clean_name = re.sub(quantity_pattern, '', food_item).strip()
            return clean_name, amount, unit
        
        return food_item, None, None

    def find_best_match(self, food_item: str, threshold: int = 60) -> Optional[Dict]:
        """Find the best matching food item in the database."""
        food_name, amount, unit = self.extract_quantity(food_item)
        food_name = self.preprocess_food_name(food_name)
        best_match = None
        best_score = 0
        
        # First try exact matches with synonyms
        base_word = None
        for key, synonyms in self.food_synonyms.items():
            if any(syn in food_name for syn in synonyms):
                base_word = key
                break
        
        # If we found a base word, prioritize matches containing it
        if base_word:
            for idx, db_name in enumerate(self.food_names):
                if base_word in db_name:
                    ratio = fuzz.ratio(food_name, db_name)
                    partial_ratio = fuzz.partial_ratio(food_name, db_name)
                    token_sort_ratio = fuzz.token_sort_ratio(food_name, db_name)
                    
                    # Give bonus points for matching the base word
                    score = max(ratio, partial_ratio, token_sort_ratio) + 20
                    
                    if score > best_score:
                        best_score = score
                        best_match = self.food_db[idx]
        
        # If no good match found with base word, try regular matching
        if best_score < threshold:
            for idx, db_name in enumerate(self.food_names):
                processed_db_name = self.preprocess_food_name(db_name)
                
                # Try different matching algorithms
                ratio = fuzz.ratio(food_name, processed_db_name)
                partial_ratio = fuzz.partial_ratio(food_name, processed_db_name)
                token_sort_ratio = fuzz.token_sort_ratio(food_name, processed_db_name)
                token_set_ratio = fuzz.token_set_ratio(food_name, processed_db_name)
                
                # Calculate weighted score
                score = max(
                    ratio * 0.3,
                    partial_ratio * 0.3,
                    token_sort_ratio * 0.2,
                    token_set_ratio * 0.2
                )
                
                # Boost score if all words in food_name are found in db_name
                food_words = set(food_name.split())
                db_words = set(processed_db_name.split())
                if food_words.issubset(db_words):
                    score += 15
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = self.food_db[idx]
        
        if best_match:
            return {
                'match': best_match,
                'confidence': min(best_score, 100),  # Cap confidence at 100
                'amount': amount,
                'unit': unit
            }
        
        # If still no match, try finding similar items
        similar_items = []
        for idx, db_name in enumerate(self.food_names):
            ratio = fuzz.ratio(food_name, db_name)
            if ratio > threshold - 20:  # Lower threshold for suggestions
                similar_items.append({
                    'name': self.food_db[idx]['name'],
                    'score': ratio
                })
        
        if similar_items:
            similar_items.sort(key=lambda x: x['score'], reverse=True)
            logging.info(f"No exact match for '{food_item}', but found similar items: {[item['name'] for item in similar_items[:3]]}")
        
        return None

    def standardize_amount(self, amount: Optional[float], unit: Optional[str]) -> float:
        """Convert amount to standard units (grams) based on common conversions."""
        if not amount:
            return 100.0  # Default to 100g if no amount specified
            
        # Conversion factors to grams
        conversions = {
            'g': 1.0,
            'ml': 1.0,  # Assuming density of 1g/ml for simplicity
            'cup': 240.0,
            'tbsp': 15.0,
            'tsp': 5.0,
            'oz': 28.35,
            'slice': 30.0,  # Approximate
            'piece': 100.0,  # Approximate
            'large': 150.0,  # Approximate
            'medium': 100.0,  # Approximate
            'small': 50.0    # Approximate
        }
        
        if unit in conversions:
            return amount * conversions[unit]
        return amount  # If unit not recognized, return original amount

    def calculate_nutrition(self, matches: List[Dict]) -> Dict[str, float]:
        """Calculate total nutrition based on matched foods and portions."""
        totals = {
            'calories': 0.0,
            'protein': 0.0,
            'carbohydrates': 0.0,
            'fat': 0.0
        }
        
        for match in matches:
            if not match:
                continue
                
            food_data = match['match']
            amount = self.standardize_amount(match['amount'], match['unit'])
            scale_factor = amount / 100.0  # USDA data is typically per 100g
            
            # Extract nutrients
            nutrients = food_data['nutrients']
            for nutrient_name, value in nutrients.items():
                if 'Energy' in nutrient_name and 'KCAL' in nutrient_name:
                    totals['calories'] += value * scale_factor
                elif 'Protein' in nutrient_name:
                    totals['protein'] += value * scale_factor
                elif 'Carbohydrate' in nutrient_name:
                    totals['carbohydrates'] += value * scale_factor
                elif 'Total lipid (fat)' in nutrient_name:
                    totals['fat'] += value * scale_factor
        
        # Round the values for better presentation
        return {k: round(v, 1) for k, v in totals.items()}

    def analyze_meal(self, food_items: List[str]) -> Dict[str, Any]:
        """Analyze a list of food items and return nutritional information."""
        matches = []
        unmatched_items = []
        similar_items_suggestions = {}
        
        for item in food_items:
            match = self.find_best_match(item)
            if match:
                matches.append(match)
            else:
                unmatched_items.append(item)
                # Try to find similar items with a lower threshold
                similar = []
                for db_name in self.food_names:
                    ratio = fuzz.ratio(self.preprocess_food_name(item), db_name)
                    if ratio > 40:  # Lower threshold for suggestions
                        similar.append((db_name, ratio))
                if similar:
                    similar.sort(key=lambda x: x[1], reverse=True)
                    similar_items_suggestions[item] = [name for name, _ in similar[:3]]
        
        nutrition = self.calculate_nutrition(matches)
        
        return {
            'nutrition': nutrition,
            'matched_items': [
                {
                    'input': item,
                    'matched_name': match['match']['name'],
                    'confidence': match['confidence'],
                    'amount': match['amount'],
                    'unit': match['unit']
                }
                for item, match in zip(food_items, matches) if match
            ],
            'unmatched_items': unmatched_items,
            'similar_items_suggestions': similar_items_suggestions
        }

def enhance_nutrition_estimate(llm_response: Dict[str, Any], food_items: List[str]) -> Dict[str, Any]:
    """Enhance LLM nutrition estimates with database values."""
    try:
        matcher = NutritionMatcher()
        db_analysis = matcher.analyze_meal(food_items)
        
        # Combine LLM and database estimates
        enhanced_response = {
            'llm_estimate': {
                'calories': llm_response.get('calories'),
                'carbohydrates': llm_response.get('carbohydrates'),
                'protein': llm_response.get('protein'),
                'fat': llm_response.get('fat'),
                'fiber': llm_response.get('fiber')
            },
            'db_estimate': db_analysis['nutrition'],
            'food_matches': db_analysis['matched_items'],
            'unmatched_items': db_analysis['unmatched_items'],
            'confidence_score': sum(m['confidence'] for m in db_analysis['matched_items']) / len(food_items) if food_items else 0
        }
        
        return enhanced_response
        
    except Exception as e:
        logging.error(f"Error enhancing nutrition estimate: {str(e)}")
        return llm_response  # Return original LLM response if enhancement fails 