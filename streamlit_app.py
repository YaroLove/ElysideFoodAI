# streamlit_app.py  (новий головний файл)

import streamlit as st
import asyncio
from dietgpt_start import CalorieEstimator, extract_nutrition
from nutrition_matcher import enhance_nutrition_estimate
from sheets_manager import SheetsManager
import os
import re
import tempfile


# --- ініціалізація -----------------------------------------------------------
api_key = st.secrets["OPENAI_API_KEY"]
if not api_key:
    st.stop()  # покаже повідомлення «API key not found»

sheets = SheetsManager()

# --- функції -----------------------------------------------------------------
def extract_food_items(response: str):
    food_section = re.search(r"Food Items:\s*((?:- [^\n]+\n?)+)", response)
    if not food_section:
        return []
    return re.findall(r"- ([^\n]+)", food_section.group(1))

async def analyze(path):
    async with CalorieEstimator(api_key=api_key) as est:
        res = await est.estimate_calories(path)
        if not res["success"]:
            return res
        nutri = extract_nutrition(res["response"])
        food  = extract_food_items(res["response"])
        enhanced = enhance_nutrition_estimate(nutri, food)
        return {
            "success": True,
            "llm_estimate": enhanced["llm_estimate"],
            "db_estimate": enhanced["db_estimate"],
            "food_items": food,
            "food_matches": enhanced["food_matches"],
            "unmatched_items": enhanced["unmatched_items"],
            "confidence_score": enhanced["confidence_score"],
            "details": res["response"],
            "image_url": f"/uploads/{os.path.basename(path)}"
        }

# --- Streamlit UI ------------------------------------------------------------
st.title("Elyside Food AI 🍽️")

user = st.selectbox("Select User", ["-- new --"] + sheets.get_users(), key="user_select")
new_user_input = None

if user == "-- new --":
    new_user_input = st.text_input("New username", key="new_username_input")
    if st.button("Add User", key="add_user_button") and new_user_input:
        # Check if user already exists (optional, but good practice)
        if new_user_input in sheets.get_users():
            st.warning("User already exists.")
        else:
            try:
                sheets.add_user(new_user_input)
                st.success(f"User '{new_user_input}' added. Please select them from the dropdown.")
                # Rerun to update the selectbox with the new user
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error adding user: {str(e)}")
    user = new_user_input # Use the new user's name for analysis if added

uploaded = st.file_uploader("Upload Food Image", type=["jpg", "jpeg", "png", "webp"])

# Only proceed if a user is selected (either existing or newly added and confirmed)
if uploaded and user and user != "-- new --":
    # тимчасово зберігаємо файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.status("Analyzing your food image...", expanded=True):
        result = asyncio.run(analyze(tmp_path))

    if result["success"]:
        st.success("Готово!")
        # st.json(result["llm_estimate"])
        
        st.subheader("Analysis Results")
        llm_estimate = result["llm_estimate"]
        st.write(f"Calories: **{llm_estimate.get('calories', 'N/A')}** kcal")
        st.write(f"Protein: **{llm_estimate.get('protein', 'N/A')}** g")
        st.write(f"Carbs: **{llm_estimate.get('carbohydrates', 'N/A')}** g")
        st.write(f"Fat: **{llm_estimate.get('fat', 'N/A')}** g")
        st.write(f"Fiber: **{llm_estimate.get('fiber', 'N/A')}** g")
        
        # Display number of unique plants
        num_unique_plants = result.get("Number_of_unique_plants_this_meal", "N/A")
        st.write(f"Number of unique plants in this meal: **{num_unique_plants}**")
        
        if st.button("Submit to Google Sheets"):
            try:
                sheets.store_analysis_result(user, result)
                st.toast("Data submitted successfully ", icon="✅")
            except Exception as e:
                st.error(f"Error submitting data: {str(e)}")
    else:
        st.error(result.get("error", "Unknown error"))
