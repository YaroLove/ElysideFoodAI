# streamlit_app.py
import streamlit as st
import asyncio, re, tempfile, os
from dietgpt_start import CalorieEstimator, extract_nutrition
from nutrition_matcher import enhance_nutrition_estimate
from sheets_manager import SheetsManager

# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Elyside Food Analysis", page_icon="🍽️", layout="centered")

# custom CSS (скопійовано з index.html, трохи адаптовано під Streamlit)
st.markdown("""
<style>
body { background:#f6f8fa; }
div[data-testid="stSidebar"] {background:#fff;}
.main-card {background:#fff;border-radius:16px;box-shadow:0 2px 16px rgba(0,0,0,0.07);padding:2rem;margin-top:2rem;}
.section-title {font-size:1.1rem;font-weight:600;margin:0 0 0.5rem;color:#1976d2;}
.nutrition-card {background:#e3f2fd;border-radius:12px;padding:1rem 1.2rem;box-shadow:0 1px 6px rgba(25,118,210,0.07);}
.plant-card {background:#f0f4c3;border-radius:12px;padding:1rem 1.2rem;box-shadow:0 1px 6px rgba(205,220,57,0.07);}
.food-image {border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);max-height:320px;object-fit:cover;}
.submit-btn {width:100%;font-size:1.05rem;padding:0.6rem 0;border-radius:8px;margin-top:1rem;}
</style>
""", unsafe_allow_html=True)
# ──────────────────────────────────────────────────────────────────────────────

sheets = SheetsManager()
api_key = st.secrets["OPENAI_API_KEY"]

def extract_food_items(text: str):
    sec = re.search(r"Food Items:\s*((?:- [^\n]+\n?)+)", text)
    return re.findall(r"- ([^\n]+)", sec.group(1)) if sec else []

async def analyze(path):
    async with CalorieEstimator(api_key=api_key) as est:
        res = await est.estimate_calories(path)
        if not res["success"]:
            return {"success": False, "error": res["response"]}

        nutri = extract_nutrition(res["response"])
        food  = extract_food_items(res["response"])
        enhanced = enhance_nutrition_estimate(nutri, food)

        return {
            "success": True,
            **enhanced,
            "details": res["response"],
            "food_items": food,
        }

# ───────────────────────────  UI  ────────────────────────────────────────────
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown("## Elyside Food Analysis")
st.caption("by Yaroslav V")

users = ["-- new --"] + sheets.get_users()
user   = st.selectbox("Select user", users)
if user == "-- new --":
    user = st.text_input("New username")

uploaded = st.file_uploader("Upload food image", type=["jpg","jpeg","png","webp"])
submit_btn = st.button("Analyze", disabled=not(uploaded and user))

if submit_btn:
    with st.spinner("Analyzing your food image…"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(uploaded.read()); tmp_path = tmp.name
        result = asyncio.run(analyze(tmp_path))

    if result["success"]:
        col_img, col_data = st.columns([1,1])
        with col_img:
            st.image(uploaded, use_column_width=True, output_format="JPEG",
                     caption="Uploaded food", clamp=True, channels="RGB",
                     **{"class": "food-image"})   # inject class for CSS
        with col_data:
            st.markdown('<div class="nutrition-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">LLM estimate</div>', unsafe_allow_html=True)
            llm = result["llm_estimate"]
            st.markdown(f"""
            Calories: **{llm.get('calories','–')} kcal**  
            Protein: **{llm.get('protein','–')} g**  
            Carbs: **{llm.get('carbohydrates','–')} g**  
            Fat: **{llm.get('fat','–')} g**  
            Fiber: **{llm.get('fiber','–')} g**
            """)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="plant-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Plant‑based ingredients</div>', unsafe_allow_html=True)
            st.write(result["food_items"])
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Submit to Google Sheets", key="submitSheets",
                         help="Save this result in the spreadsheet"):
                sheets.store_analysis_result(user, result)
                st.success("Saved to Google Sheets!")

    else:
        st.error(result["error"])

st.markdown('</div>', unsafe_allow_html=True)  # close main-card
