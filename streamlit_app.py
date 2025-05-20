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

user = st.selectbox("Select User", ["-- new --"] + sheets.get_users())
if user == "-- new --":
    user = st.text_input("New username")

uploaded = st.file_uploader("Upload Food Image", type=["jpg", "jpeg", "png", "webp"])

if uploaded and user:
    # тимчасово зберігаємо файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.status("Analyzing your food image...", expanded=True):
        result = asyncio.run(analyze(tmp_path))

    if result["success"]:
        st.success("Готово!")
        st.json(result["llm_estimate"])
        if st.button("Submit to Google Sheets"):
            try:
                sheets.store_analysis_result(user, result)
                st.toast("Data submitted successfully ", icon="✅")
            except Exception as e:
                st.error(f"Error submitting data: {str(e)}")
    else:
        st.error(result.get("error", "Unknown error"))
