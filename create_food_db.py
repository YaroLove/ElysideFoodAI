import pandas as pd
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def load_data():
    logging.info("Starting to load USDA data files...")
    
    logging.info("Loading food.csv...")
    food_df = pd.read_csv('usda/food.csv', low_memory=False)
    logging.info(f"Loaded {len(food_df)} food items")
    
    logging.info("Loading food_nutrient.csv...")
    food_nutrients_df = pd.read_csv('usda/food_nutrient.csv', low_memory=False)
    logging.info(f"Loaded {len(food_nutrients_df)} nutrient entries")
    
    logging.info("Loading nutrient.csv...")
    nutrients_df = pd.read_csv('usda/nutrient.csv', low_memory=False)
    logging.info(f"Loaded {len(nutrients_df)} nutrient definitions")
    
    logging.info("Loading food_category.csv...")
    categories_df = pd.read_csv('usda/food_category.csv', low_memory=False)
    logging.info(f"Loaded {len(categories_df)} food categories")
    
    valid_types = ['sr_legacy_food', 'foundation_food', 'survey_fndds_food']
    logging.info("Filtering food items by valid types...")
    food_df = food_df[food_df['data_type'].isin(valid_types)]
    logging.info(f"Retained {len(food_df)} food items after filtering")
    
    return food_df, food_nutrients_df, nutrients_df, categories_df

def process_nutrients(food_df, food_nutrients_df, nutrients_df):
    logging.info("Merging nutrient data...")
    nutrients_merged = pd.merge(
        food_nutrients_df,
        nutrients_df,
        left_on='nutrient_id',
        right_on='id'
    ).drop_duplicates(subset=['fdc_id', 'nutrient_id', 'unit_name'])
    logging.info(f"Merged data contains {len(nutrients_merged)} entries")

    logging.info("Filtering nutrients for valid food items...")
    nutrients_merged = nutrients_merged[nutrients_merged['fdc_id'].isin(food_df['fdc_id'])]
    logging.info(f"Retained {len(nutrients_merged)} entries after filtering")
    
    logging.info("Cleaning energy units...")
    clean_nutrients = nutrients_merged[
        ~((nutrients_merged['name'] == 'Energy') & (nutrients_merged['unit_name'] != 'KCAL'))
    ]
    logging.info(f"Final nutrient dataset contains {len(clean_nutrients)} entries")
    
    return clean_nutrients

def analyze_nutrient_coverage(nutrients_merged, food_df):
    logging.info("Analyzing nutrient coverage...")
    total_foods = len(food_df)
    nutrient_counts = nutrients_merged.groupby('name').size()
    threshold = 0.005 * total_foods
    nutrient_counts = nutrient_counts[nutrient_counts >= threshold]
    
    logging.info(f"\nFound {len(nutrient_counts)} unique nutrients in {total_foods} foods")
    logging.info("\nNutrient Coverage (sorted by frequency):")
    logging.info("-" * 80)

    for nutrient, count in sorted(nutrient_counts.items(), key=lambda x: (x[1] / total_foods), reverse=True):
        percentage = (count / total_foods) * 100
        logging.info(f"{nutrient:<50} {percentage:6.3f}% ({count:>8} occurrences)")

    return nutrient_counts

def process_food_items(food_df, nutrients_merged, nutrient_counts):
    logging.info("Starting to process individual food items...")
    data = []
    total_items = len(food_df)
    logging.info(f"Total items to process: {total_items}")

    for idx, (_, food_row) in enumerate(food_df.iterrows(), 1):
        if idx % 1000 == 0:
            logging.info(f"Processing food item {idx}/{total_items} ({(idx/total_items)*100:.1f}%)")

        food_nutrients = nutrients_merged[
            (nutrients_merged['fdc_id'] == food_row['fdc_id']) &
            (nutrients_merged['name'].isin(nutrient_counts.index))
        ]

        food_item = {
            "name": food_row['description'],
            "fdc_id": food_row['fdc_id'],
            "nutrients": {}
        }

        for _, nutrient in food_nutrients.iterrows():
            if pd.notna(nutrient['amount']):
                column_name = f"{nutrient['name'].strip()} ({nutrient['unit_name']})"
                food_item['nutrients'][column_name] = nutrient['amount']

        data.append(food_item)

    logging.info(f"Completed processing {len(data)} food items")
    return data

def main():
    try:
        logging.info("Starting food database creation...")
        
        food_df, food_nutrients_df, nutrients_df, categories_df = load_data()
        logging.info("Data loading complete")
        
        nutrients_merged = process_nutrients(food_df, food_nutrients_df, nutrients_df)
        logging.info("Nutrient processing complete")
        
        nutrient_counts = analyze_nutrient_coverage(nutrients_merged, food_df)
        logging.info("Nutrient coverage analysis complete")
        
        data = process_food_items(food_df, nutrients_merged, nutrient_counts)
        logging.info("Food item processing complete")

        output_file = 'food_db.json'
        logging.info(f"Exporting {len(data)} food items to {output_file}")

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logging.info("Export complete")
        
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 