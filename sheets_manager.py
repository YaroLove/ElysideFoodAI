# sheets_manager.py
import requests, json, re
from datetime import datetime

SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzTYZsWua8jcshxso13O8CoIhgevSkPKmyDrWLqTvo3NwAUIDJFyuNuhFbZXbuas8YD/exec"
)

class SheetsManager:
    """Thin wrapper around Apps‑Script web‑app used as JSON API for Google Sheets."""

    # ──────────────────────────────── READ ──────────────────────────────────
    def get_users(self) -> list[str]:
        try:
            r = requests.get(SCRIPT_URL, params={"path": "Users", "action": "read"}, timeout=10)
            data = r.json()
            return [row["Users"] for row in data.get("data", []) if row.get("Users")]
        except Exception as e:
            print("Error get_users:", e)
            return []

    # ──────────────────────────────── WRITE (single cell) ───────────────────
    def add_user(self, username: str) -> str:
        try:
            r = requests.get(
                SCRIPT_URL,
                params={"path": "Users", "action": "write", "Users": username},
                timeout=10,
            )
            return r.text
        except Exception as e:
            return f"Error add_user: {e}"

    # ──────────────────────────────── WRITE (one row) ───────────────────────
    def store_analysis_result(self, username: str, result: dict) -> str:
        """Append one row to ‘Results’ via GET => doGet(action='write')."""
        try:
            plants = result.get("food_items", [])
            row = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Username": username,
                "Calories":   result["llm_estimate"].get("calories", ""),
                "Protein":    result["llm_estimate"].get("protein", ""),
                "Carbs":      result["llm_estimate"].get("carbohydrates", ""),
                "Fat":        result["llm_estimate"].get("fat", ""),
                "Fiber":      result["llm_estimate"].get("fiber", ""),
                "Number_of_unique_plants_this_meal": len(set(plants)),
                "Plant_based_Ingredients": ", ".join(plants),
                "Image_URL":  result["image_url"].split("/")[-1],
            }

            params = {"path": "Results", "action": "write", **row}
            print("⇢ sending GET → Sheets\n", json.dumps(params, indent=2, ensure_ascii=False))

            r = requests.get(SCRIPT_URL, params=params, timeout=10)
            print("⇠ Google Sheets status:", r.status_code, r.text[:120])
            r.raise_for_status()
            return r.text
        except Exception as e:
            return f"Error storing result: {e}"

    # ──────────────────────────────── READ (history) ────────────────────────
    def get_user_results(self, username: str) -> list[dict]:
        try:
            r = requests.get(SCRIPT_URL, params={"path": "Results", "action": "read"}, timeout=10)
            data = r.json()
            return [row for row in data.get("data", []) if row.get("Username") == username]
        except Exception as e:
            print("Error get_user_results:", e)
            return []
