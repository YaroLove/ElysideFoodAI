import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import asyncio
from dietgpt_start import CalorieEstimator, extract_nutrition
from nutrition_matcher import enhance_nutrition_estimate
from dotenv import load_dotenv
import re
from sheets_manager import SheetsManager

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Initialize Sheets Manager
sheets_manager = SheetsManager()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_food_items(response: str) -> list:
    # Find the "Food Items:" section and extract all items
    food_section = re.search(r'Food Items:\s*((?:- [^\n]+\n?)+)', response)
    if not food_section:
        return []
    
    # Extract individual items
    items = re.findall(r'- ([^\n]+)', food_section.group(1))
    return items

# Load API key once at startup
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

async def analyze_food_image(image_path):
    async with CalorieEstimator(api_key=api_key) as estimator:
        result = await estimator.estimate_calories(image_path)
        if result['success']:
            nutrition = extract_nutrition(result['response'])
            food_items = extract_food_items(result['response'])
            
            # Enhance nutrition estimates with database values
            enhanced_result = enhance_nutrition_estimate(nutrition, food_items)
            
            return {
                'success': True,
                'llm_estimate': enhanced_result['llm_estimate'],
                'db_estimate': enhanced_result['db_estimate'],
                'food_items': food_items,
                'food_matches': enhanced_result['food_matches'],
                'unmatched_items': enhanced_result['unmatched_items'],
                'confidence_score': enhanced_result['confidence_score'],
                'details': result['response']
            }
        return {
            'success': False,
            'error': 'Failed to analyze food image'
        }

@app.route('/')
def home():
    # Get list of users for the dropdown
    users = sheets_manager.get_users()
    return render_template('index.html', users=users)

@app.route('/users', methods=['GET'])
def get_users():
    users = sheets_manager.get_users()
    return jsonify(users)

@app.route('/users', methods=['POST'])
def add_user():
    username = request.json.get('username')
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    try:
        sheets_manager.add_user(username)
        return jsonify({'success': True, 'message': 'User added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/estimate', methods=['POST'])
def estimate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    username = request.form.get('username')
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Run food analysis
        result = asyncio.run(analyze_food_image(filepath))
        
        print("RESULT TO FRONTEND:", result)
        
        if result['success']:
            return jsonify({
                'success': True,
                'llm_estimate': result['llm_estimate'],
                'db_estimate': result['db_estimate'],
                'food_items': result['food_items'],
                'food_matches': result['food_matches'],
                'unmatched_items': result['unmatched_items'],
                'confidence_score': result['confidence_score'],
                'details': result['details'],
                'image_url': f'/uploads/{filename}'
            })
        else:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/user-results/<username>')
def get_user_results(username):
    try:
        results = sheets_manager.get_user_results(username)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/submit-analysis', methods=['POST'])
def submit_analysis():
    try:
        data = request.get_json()
        username = data.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400
        sheets_manager.store_analysis_result(username, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True) 