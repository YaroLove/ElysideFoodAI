import streamlit as st
import asyncio, re, tempfile, base64
from dietgpt_start import CalorieEstimator, extract_nutrition
from nutrition_matcher import enhance_nutrition_estimate
from sheets_manager import SheetsManager

# ────────────── Page config ────────────────────────────────────────────────
st.set_page_config("Elyside Food Analysis", "🍽️", layout="centered")

# ────────────── CSS ────────────────────────────────────────────────────────
st.markdown(
    """
<style>
body {background:#f6f8fa;}
.section-title{font-size:1.2rem;font-weight:600;margin-bottom:12px;color:#1976d2;}
.nutrition-card{background:#e3f2fd;border-radius:12px;padding:20px 24px;margin-bottom:18px;
                box-shadow:0 1px 6px rgba(25,118,210,0.07);}
.plant-card{background:#f0f4c3;border-radius:12px;padding:18px 24px;margin-bottom:18px;
            box-shadow:0 1px 6px rgba(205,220,57,0.07);}
img.food-image{border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);
               margin-bottom:18px;max-height:320px;object-fit:cover;width:100%;}
</style>
""",
    unsafe_allow_html=True,
)

# ────────────── Helpers ────────────────────────────────────────────────────
sheets = SheetsManager()
api_key = st.secrets["OPENAI_API_KEY"]

def extract_food_items(text: str) -> list[str]:
    """Пункти після 'Food Items:'"""
    m = re.search(r"Food Items?:\s*([\s\S]*?)(?:\n\s*\n|$)", text, re.I)
    if not m:
        return []
    lines = [re.sub(r"^-+\s*", "", l).strip() for l in m.group(1).splitlines()]
    return [l for l in lines if l]

def extract_plants(text: str) -> list[str]:
    """Пункти після 'Plant‑based Ingredients:'"""
    m = re.search(r"Plant-based Ingredients?:\s*([\s\S]*?)(?:\n\s*\n|$)", text, re.I)
    if not m:
        return []
    lines = [re.sub(r"^-+\s*", "", l).strip() for l in m.group(1).splitlines()]
    return [l for l in lines if l]

async def analyze(path: str):
    async with CalorieEstimator(api_key=api_key) as est:
        res = await est.estimate_calories(path)
        if not res["success"]:
            return {"success": False, "error": res["response"]}

        llm_nutri = extract_nutrition(res["response"])
        plant_items = extract_plants(res["response"])
        enhanced = enhance_nutrition_estimate(llm_nutri, plant_items)

        return {
            "success": True,
            **enhanced,
            "plant_items": plant_items,
            "details": res["response"],
            "image_url": path,
        }

# ────────────── UI ────────────────────────────────────────────────────────
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<h1 class="text-center mb-2">Elyside Food Analysis</h1>', unsafe_allow_html=True)
st.markdown('<p class="text-center text-muted fst-italic mb-4">by Yaroslav V</p>', unsafe_allow_html=True)

# user row
c1, c2 = st.columns(2, gap="medium")
with c1:
    users = ["-- new --"] + sheets.get_users()
    user  = st.selectbox("Select user", users)
with c2:
    new_user = st.text_input("New username")
    if st.button("Add User") and new_user.strip():
        sheets.add_user(new_user.strip())
        st.success("User added!")
        st.experimental_rerun()

if user == "-- new --":
    user = new_user.strip()

# upload & analyze
upl = st.file_uploader("Upload food image", type=["jpg","jpeg","png","webp"])
if st.button("Analyze", disabled=not(upl and user)):
    with st.spinner("Analyzing…"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
            tf.write(upl.read()); tmp_path = tf.name
        result = asyncio.run(analyze(tmp_path))

    if not result["success"]:
        st.error(result["error"])
    else:
        ci, cd = st.columns([1,1], gap="large")
        with ci:
            b64 = base64.b64encode(open(tmp_path,"rb").read()).decode()
            st.markdown(f'<img src="data:image/jpeg;base64,{b64}" class="food-image"/>',
                        unsafe_allow_html=True)
        with cd:
            st.markdown('<div class="nutrition-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">LLM estimate</div>', unsafe_allow_html=True)
            n = result["llm_estimate"]
            st.markdown(f"""
            Calories: **{n.get('calories','–')} kcal**  
            Protein: **{n.get('protein','–')} g**  
            Carbs: **{n.get('carbohydrates','–')} g**  
            Fat: **{n.get('fat','–')} g**  
            Fiber: **{n.get('fiber','–')} g**
            """)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="plant-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Plant‑based ingredients</div>', unsafe_allow_html=True)
            st.markdown("<ul>" + "".join(f"<li>{p}</li>" for p in result["plant_items"]) + "</ul>",
                        unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Submit to Google Sheets"):
                resp = sheets.store_analysis_result(user, result)
                st.success("Saved! Google replied: " + resp)
