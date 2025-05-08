# streamlit_app.py
import streamlit as st
import asyncio, re, tempfile, base64
from dietgpt_start import CalorieEstimator, extract_nutrition
from nutrition_matcher import enhance_nutrition_estimate
from sheets_manager import SheetsManager

# ────────────── Page config ─────────────────────────────────────────────────
st.set_page_config("Elyside Food Analysis", "🍽️", layout="centered")

# ────────────── CSS (адаптовано з index.html) ───────────────────────────────
st.markdown(
    """
<style>
body {background:#f6f8fa;}
.main-card {background:#fff;border-radius:16px;
            box-shadow:0 2px 16px rgba(0,0,0,0.07);
            padding:32px 32px 24px;margin:40px auto;max-width:800px;}
.section-title{font-size:1.2rem;font-weight:600;margin-bottom:12px;color:#1976d2;}
.nutrition-card{background:#e3f2fd;border-radius:12px;padding:20px 24px;margin-bottom:18px;
                box-shadow:0 1px 6px rgba(25,118,210,0.07);}
.plant-card{background:#f0f4c3;border-radius:12px;padding:18px 24px;margin-bottom:18px;
            box-shadow:0 1px 6px rgba(205,220,57,0.07);}
img.food-image{border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);
               margin-bottom:18px;max-height:320px;object-fit:cover;width:100%;}
.submit-btn{width:100%;font-size:1.1rem;padding:12px 0;border-radius:8px;margin-top:18px;}
</style>
""",
    unsafe_allow_html=True,
)

# ────────────── Helpers ─────────────────────────────────────────────────────
sheets = SheetsManager()
api_key = st.secrets["OPENAI_API_KEY"]

def extract_food_items(text: str):
    """
    Витягає список після 'Food Items:' до першого порожнього рядка /
    подвійного переносу.
    """
    sec = re.search(r"Food Items?:\s*([\s\S]*?)(?:\n\s*\n|$)", text, re.IGNORECASE)
    if not sec:
        return []
    lines = [re.sub(r"^-+\s*", "", l).strip() for l in sec.group(1).splitlines()]
    return [l for l in lines if l]

async def analyze(path: str):
    async with CalorieEstimator(api_key=api_key) as est:
        res = await est.estimate_calories(path)
        if not res["success"]:
            return {"success": False, "error": res["response"]}

        nutri   = extract_nutrition(res["response"])
        plants  = extract_food_items(res["response"])
        enhanced = enhance_nutrition_estimate(nutri, plants)

        return {
            "success": True,
            **enhanced,
            "details": res["response"],
            "food_items": plants,
            "image_url": path,
        }

# ────────────── UI ──────────────────────────────────────────────────────────
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<h1 class="text-center mb-2">Elyside Food Analysis</h1>', unsafe_allow_html=True)
st.markdown('<p class="text-center text-muted fst-italic mb-4">by Yaroslav V</p>', unsafe_allow_html=True)

# ── user management row ─────────────────────────────────────────────────────
col_sel, col_new = st.columns(2, gap="medium")
with col_sel:
    users = ["-- new --"] + sheets.get_users()
    user  = st.selectbox("User selector (hidden label)",
                         users,
                         label_visibility="collapsed")
with col_new:
    new_username = st.text_input("New username (hidden label)",
                                 placeholder="New username",
                                 label_visibility="collapsed")
    if st.button("Add User", use_container_width=True) and new_username.strip():
        sheets.add_user(new_username.strip())
        st.success("User added!")
        st.experimental_rerun()

if user == "-- new --":
    user = new_username.strip()

# ── upload & analyze ───────────────────────────────────────────────────────
uploaded    = st.file_uploader("Upload Food Image", type=["jpg","jpeg","png","webp"])
analyze_btn = st.button("Analyze",
                        disabled=not(uploaded and user),
                        use_container_width=True)

if analyze_btn and uploaded:
    with st.spinner("Analyzing your food image…"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(uploaded.read()); tmp_path = tmp.name
        result = asyncio.run(analyze(tmp_path))

    if result["success"]:
        # ── result layout ───────────────────────────────────────────────────
        col_img, col_data = st.columns([1,1], gap="large")

        # image
        with col_img:
            img_b64 = base64.b64encode(open(tmp_path, "rb").read()).decode()
            st.markdown(
                f'<img src="data:image/jpeg;base64,{img_b64}" class="food-image"/>',
                unsafe_allow_html=True
            )

        # nutrition + plants
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
            plants_html = "".join(f"<li>{p}</li>" for p in result["food_items"])
            st.markdown(f"<ul>{plants_html}</ul>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Submit to Google Sheets",
                         key="submitData",
                         type="primary",
                         use_container_width=True):
                sheets.store_analysis_result(user, result)
                st.success("Data submitted successfully!")

    else:
        st.error(result["error"])
