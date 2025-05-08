import logging
import base64
import io
import re
import os
import asyncio
import aiohttp
import streamlit as st
import openai

from datetime import datetime
from PIL import Image
import pandas as pd
from tenacity import (
    retry, wait_exponential, stop_after_attempt, retry_if_exception_type
)
from tqdm import tqdm
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPT
import ssl
import certifi
import time
import random
from typing import List, Dict, Any, Optional
from io import BytesIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('diet_gpt.log'),
        logging.StreamHandler()
    ]
)

# Create SSL context with certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

class CalorieEstimator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.system_prompt = SYSTEM_PROMPT
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.model = "gpt-4o-mini"
        self.session = None
        self.semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        self.retry_delay = 1.0  # Initial retry delay in seconds
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
    async def __aenter__(self):
        await self.create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
        
    async def create_session(self):
        if not self.session:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def encode_image(self, image_path: str) -> str:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Resize if the image is too large
            max_size = 768
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            # Convert to JPEG and encode
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def estimate_calories(self, image_path: str, max_retries: int = 5) -> Dict[str, Any]:
        if not self.session:
            await self.create_session()
            
        async with self.semaphore:  # Limit concurrent requests
            retry_count = 0
            current_delay = self.retry_delay

            while retry_count < max_retries:
                try:
                    base64_image = self.encode_image(image_path)
                    
                    payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": self.system_prompt
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Please analyze this food image and estimate the total calories."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 150
                    }

                    async with self.session.post(self.api_url, headers=self.headers, json=payload) as response:
                        if response.status == 429:  # Rate limit exceeded
                            retry_after = float(response.headers.get('Retry-After', current_delay))
                            await asyncio.sleep(retry_after)
                            current_delay = min(current_delay * 2, 60)  # Exponential backoff, max 60 seconds
                            retry_count += 1
                            continue

                        response.raise_for_status()
                        result = await response.json()
                        
                        if 'error' in result:
                            if 'Rate limit' in result['error'].get('message', ''):
                                await asyncio.sleep(current_delay)
                                current_delay = min(current_delay * 2, 60)
                                retry_count += 1
                                continue
                            raise Exception(f"API request failed: {result}")

                        return {
                            'response': result['choices'][0]['message']['content'],
                            'success': True
                        }

                except Exception as e:
                    logging.error(f"Error processing {image_path}: {str(e)}")
                    if retry_count < max_retries - 1:
                        await asyncio.sleep(current_delay)
                        current_delay = min(current_delay * 2, 60)
                        retry_count += 1
                    else:
                        return {
                            'response': "Max retries exceeded",
                            'success': False
                        }

            return {
                'response': "Max retries exceeded",
                'success': False
            }

    async def process_images(self, image_paths: List[str]) -> pd.DataFrame:
        await self.create_session()
        
        results = []
        batch_size = 5  # Process images in small batches
        
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            tasks = [self.estimate_calories(img_path) for img_path in batch]
            batch_results = await asyncio.gather(*tasks)
            
            for img_path, result in zip(batch, batch_results):
                print(f"LLM Output: {result['response']}")
                results.append({
                    'image_path': img_path,
                    'response': result['response'],
                    'success': result['success']
                })
            
            # Add a small delay between batches
            await asyncio.sleep(2)
        
        await self.close_session()
        return pd.DataFrame(results)

def extract_nutrition(response: str) -> Dict[str, Optional[float]]:
    print("LLM RAW RESPONSE:\n", response)
    try:
        nutrition = {
            'calories': None,
            'carbohydrates': None,
            'protein': None,
            'fat': None,
            'fiber': None
        }
        # Extract calories
        calories_pattern = r'^CALORIES:\s*(\d+)'
        match = re.search(calories_pattern, response.strip())
        if match:
            nutrition['calories'] = float(match.group(1))
        else:
            calories_pattern = r'CALORIES:\s*(\d+)'
            match = re.search(calories_pattern, response)
            if match:
                nutrition['calories'] = float(match.group(1))
        # Extract macronutrients
        carbs_pattern = r'Carbohydrates:\s*(\d+)g'
        protein_pattern = r'Protein:\s*(\d+)g'
        fat_pattern = r'Fat:\s*(\d+)g'
        fiber_pattern = r'Fiber[:\s]*([\d\.]+)g|Fibre[:\s]*([\d\.]+)g|Dietary fiber[:\s]*([\d\.]+)g'
        carbs_match = re.search(carbs_pattern, response)
        protein_match = re.search(protein_pattern, response)
        fat_match = re.search(fat_pattern, response)
        fiber_match = re.search(fiber_pattern, response, re.IGNORECASE)
        if carbs_match:
            nutrition['carbohydrates'] = float(carbs_match.group(1))
        if protein_match:
            nutrition['protein'] = float(protein_match.group(1))
        if fat_match:
            nutrition['fat'] = float(fat_match.group(1))
        if fiber_match:
            fiber_val = next((g for g in fiber_match.groups() if g), None)
            if fiber_val is not None:
                nutrition['fiber'] = float(fiber_val)
        return nutrition
    except Exception as e:
        logging.error(f"Error extracting nutrition: {str(e)}")
        return {
            'calories': None,
            'carbohydrates': None,
            'protein': None,
            'fat': None,
            'fiber': None
        }

async def process_single_image(estimator, image_path, actual_calories=None):
    try:
        result = await estimator.estimate_calories(image_path)
        if result.get('success'):
            nutrition = extract_nutrition(result.get('response', ''))
            if nutrition['calories'] is not None:
                return {
                    'image': os.path.basename(image_path),
                    'actual_calories': float(actual_calories) if actual_calories else None,
                    'estimated_calories': nutrition['calories'],
                    'estimated_carbs': nutrition['carbohydrates'],
                    'estimated_protein': nutrition['protein'],
                    'estimated_fat': nutrition['fat'],
                    'estimated_fiber': nutrition['fiber'],
                    'calorie_difference': abs(nutrition['calories'] - float(actual_calories)) if actual_calories else None,
                    'llm_output': result.get('response', 'N/A'),
                    'success': True
                }
        logging.error(f"Error processing {image_path}: {result.get('response', 'Unknown error')}\nLLM Output: {result.get('response', 'No output')}")
        return None
    except Exception as e:
        logging.error(f"Exception processing {image_path}: {str(e)}")
        return None

async def main():
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(script_dir, 'DATASET')
    results_dir = os.path.join(script_dir, "estimation_results")
    
    # Load API key
    load_dotenv()
    api_key = st.secrets['OPENAI_API_KEY']
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    # Add debug logging
    logging.info(f"API Key loaded: {api_key[:8]}...{api_key[-4:]}")
    if not (api_key.startswith('sk-') or api_key.startswith('sk-proj-')):
        logging.error("API key does not start with 'sk-' or 'sk-proj-'. Please check your API key format.")
        raise ValueError("Invalid API key format")

    # Create results directory
    os.makedirs(results_dir, exist_ok=True)
    
    async with CalorieEstimator(api_key=api_key) as estimator:
        try:
            # Load and process the dataset
            csv_path = os.path.join(dataset_path, 'processed_labels.csv')
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found at {csv_path}")
                
            df = pd.read_csv(csv_path).dropna(subset=['calories'])
            
            # Process images in smaller batches to manage rate limits
            batch_size = 5
            results = []
            
            for i in range(0, len(df), batch_size):
                batch_df = df.iloc[i:i + batch_size]
                tasks = [
                    process_single_image(
                        estimator,
                        os.path.join(dataset_path, row['img_path']),
                        row['calories']
                    )
                    for _, row in batch_df.iterrows()
                    if os.path.exists(os.path.join(dataset_path, row['img_path']))
                ]
                
                # Process batch with progress bar
                with tqdm(total=len(tasks), desc=f"Processing batch {i//batch_size + 1}") as pbar:
                    batch_results = await asyncio.gather(*tasks)
                    for result in batch_results:
                        if result:
                            results.append(result)
                        pbar.update(1)
                
                # Add delay between batches
                await asyncio.sleep(2)
            
            if results:
                # Save results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(results_dir, f"estimation_openai_{timestamp}.csv")
                pd.DataFrame(results).to_csv(output_file, index=False)
                logging.info(f"Results saved to {output_file}")
                
                # Calculate and display statistics
                df_results = pd.DataFrame(results)
                if 'calorie_difference' in df_results.columns:
                    mean_diff = df_results['calorie_difference'].mean()
                    median_diff = df_results['calorie_difference'].median()
                    logging.info(f"Average calorie difference: {mean_diff:.2f}")
                    logging.info(f"Median calorie difference: {median_diff:.2f}")
            else:
                logging.warning("No results were generated")
                
        except Exception as e:
            logging.error(f"Error in main execution: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(main()) 
