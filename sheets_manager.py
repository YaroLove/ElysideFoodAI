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
            plant_items = []
            if 'plant_items' in result and isinstance(result['plant_items'], list):
                plant_items = result['plant_items']
            elif 'details' in result:
                plant_section = re.search(r'Plant-based Ingredients:\s*((?:- [^\n]+\n?)+)', result['details'])
                if plant_section:
                    plant_items = re.findall(r'- ([^\n]+)', plant_section.group(1))
            
            # Кількість унікальних рослин у цьому прийомі їжі (без нормалізації)
            num_unique_plants = len(set([p.strip() for p in plant_items]))
            
            # Ensure all required fields are present
            llm_estimate = result.get('llm_estimate', {})
            row_data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Username': username,
                'Calories': llm_estimate.get('calories', 0),
                'Protein': llm_estimate.get('protein', 0),
                'Carbs': llm_estimate.get('carbohydrates', 0),
                'Fat': llm_estimate.get('fat', 0),
                'Fiber': llm_estimate.get('fiber', 0),
                'Number_of_unique_plants_this_meal': num_unique_plants,
                'Plant_based_Ingredients': ', '.join([p.strip() for p in plant_items]),
                'Image_URL': result.get('image_url', '').replace('/uploads', '')
            }
            
            payload = {
                'path': 'Results',
                'rowData': row_data
            }
            
            print("Sending to Google Sheets:", json.dumps(payload, indent=2))
            response = requests.post(SCRIPT_URL, json=payload)
            
            if response.status_code != 200:
                print(f"Error response from Google Sheets: {response.text}")
                return f"Error: {response.text}"
                
            response_data = response.json()
            if 'error' in response_data:
                print(f"Error from Google Sheets: {response_data['error']}")
                return f"Error: {response_data['error']}"
                
            return response.text
        except Exception as e:
            print(f"Error storing result: {str(e)}")
            return f"Error storing result: {str(e)}"

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
