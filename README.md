# Elyside DietGPT

An AI-powered food image analysis tool that estimates calorie content and nutritional information from photos.

## Features

- **Web Interface**:
  - Modern, responsive design
  - Drag-and-drop image upload
  - Real-time calorie estimation
  - Macronutrient breakdown (Carbs, Protein, Fat)
  - Ingredient list detection
  - Mobile-friendly interface

- **CLI Tool**:
  - Batch processing of images
  - CSV export of results
  - Progress tracking with detailed logging
  - Automatic image optimization
  - Support for multiple image formats

- **Core Capabilities**:
  - Accurate food item identification
  - Portion size estimation
  - Calorie content calculation
  - Macronutrient analysis
  - Ingredient detection
  - Support for complex, multi-component meals

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Web Interface
1. Start the web server:
```bash
python app.py
```
2. Open your browser and navigate to `http://localhost:5003`
3. Upload an image through the interface or drag and drop
4. View the analysis results in real-time

### CLI Tool
1. Place your food images in the `DATASET` directory
2. Create a `processed_labels.csv` file in the DATASET directory (optional, for validation)
3. Run the analysis:
```bash
python dietgpt_start.py
```
4. Results will be saved in `estimation_results/estimation_openai_[timestamp].csv`

## Input Formats

The tool supports:
- Image formats: PNG, JPG, JPEG, WEBP
- Automatic image optimization:
  - RGB color space conversion
  - Smart resizing for large images
  - Quality optimization for API processing

## Output Format

### Web Interface
- Total calories
- Macronutrient breakdown:
  - Carbohydrates (g)
  - Protein (g)
  - Fat (g)
- List of detected ingredients

### CLI Output
CSV file containing:
- Image name
- Estimated calories
- Actual calories (if provided)
- Calorie difference
- Detailed analysis
- Success status

## Error Handling

- Automatic retries for API failures
- Detailed error logging
- Input validation
- Graceful failure handling
- User-friendly error messages

## Technical Details

- Built with Flask for the web interface
- Uses OpenAI's GPT-4 Vision API
- Asynchronous processing for better performance
- Rate limiting and request optimization
- Secure file handling and validation

## Contributing

Feel free to submit issues and pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/) 