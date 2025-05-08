import requests
import json
from datetime import datetime
import re

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzTYZsWua8jcshxso13O8CoIhgevSkPKmyDrWLqTvo3NwAUIDJFyuNuhFbZXbuas8YD/exec"

class SheetsManager:
    def __init__(self):
        pass

    def get_users(self):
        """Get list of all users from the spreadsheet"""
        try:
            response = requests.get(SCRIPT_URL, params={
                'path': 'Users',
                'action': 'read'
            })
            data = response.json()
            if 'data' in data:
                return [user['Users'] for user in data['data'] if user['Users']]
            return []
        except Exception as e:
            print(f"Error getting users: {str(e)}")
            return []

    def add_user(self, username):
        """Add a new user to the spreadsheet"""
        try:
            response = requests.get(SCRIPT_URL, params={
                'path': 'Users',
                'action': 'write',
                'Users': username
            })
            return response.text
        except Exception as e:
            print(f"Error adding user: {str(e)}")
            return "Error adding user"

    def store_analysis_result(self, username, result):
        """Store analysis result in the spreadsheet"""
        try:
            plant_items = result.get("plant_items", [])
            row_data = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Username": username,
                "Calories": result["llm_estimate"].get("calories"),
                "Protein":  result["llm_estimate"].get("protein"),
                "Carbs":    result["llm_estimate"].get("carbohydrates"),
                "Fat":      result["llm_estimate"].get("fat"),
                "Fiber":    result["llm_estimate"].get("fiber"),
                "Number_of_unique_plants_this_meal": len(set(plant_items)),
                "Plant_based_Ingredients": ", ".join(plant_items),
                "Image_URL": result["image_url"].split("/")[-1],   # лишаємо тільки файл
            }
            payload = {"path": "Results", "rowData": row_data}
            print("Sending to sheets:", json.dumps(payload, indent=2))
            r = requests.post(SCRIPT_URL, json=payload, timeout=10)
            return r.text
        except Exception as e:
            return f"Error storing result: {e}"


    def get_user_results(self, username):
        """Get all analysis results for a specific user"""
        try:
            response = requests.get(SCRIPT_URL, params={
                'path': 'Results',
                'action': 'read'
            })
            data = response.json()
            if 'data' in data:
                # Filter results for the specific user
                user_results = [
                    {
                        'timestamp': row['Timestamp'],
                        'llm_calories': row['LLM_Calories'],
                        'db_calories': row['DB_Calories'],
                        'fiber': row['Fiber'],  # New field
                        'food_items': json.loads(row['Food_Items']),
                        'plant_items': json.loads(row['Plant_Items']),  # New field
                        'image_url': row['Image_URL']
                    }
                    for row in data['data']
                    if row['Username'] == username
                ]
                return user_results
            return []
        except Exception as e:
            print(f"Error getting user results: {str(e)}")
            return [] 
