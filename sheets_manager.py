# sheets_manager.py  — версія лише з GET‑запитами
import requests, json, re
from datetime import datetime

SCRIPT_URL = (
    "https://script.google.com/macros/s/AKfycbzTYZsWua8jcshxso13O8CoIhgevSkPKmyDrWLqTvo3NwAUIDJFyuNuhFbZXbuas8YD/exec"
)


class SheetsManager:
    # ──────────── низькорівневий виклик ────────────
    def _get(self, params: dict):
        try:
            r = requests.get(SCRIPT_URL, params=params, timeout=10)
            r.raise_for_status()
            # якщо Apps Script повертає JSON – розбираємо
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
            return r.text
        except Exception as e:
            print("⇢ Google Sheets error:", e)
            return None

    # ──────────────── Users лист ───────────────────
    def get_users(self) -> list[str]:
        data = self._get({"path": "Users", "action": "read"})
        if isinstance(data, dict) and "data" in data:
            return [row["Users"] for row in data["data"] if row["Users"]]
        return []

    def add_user(self, username: str) -> str:
        return str(
            self._get(
                {
                    "path": "Users",
                    "action": "write",
                    "Users": username,
                }
            )
        )

    # ──────────────── Results лист ─────────────────
def store_analysis_result(self, username: str, result: dict) -> str:
        """Append one row to ‘Results’ sheet via GET → doGet(action='write')."""
        try:
            plants = result.get("food_items", [])
            row = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Username":   username,
                "Calories":   result["llm_estimate"].get("calories", ""),
                "Protein":    result["llm_estimate"].get("protein", ""),
                "Carbs":      result["llm_estimate"].get("carbohydrates", ""),
                "Fat":        result["llm_estimate"].get("fat", ""),
                "Fiber":      result["llm_estimate"].get("fiber", ""),
                "Number_of_unique_plants_this_meal": len(set(plants)),
                "Plant_based_Ingredients": ", ".join(plants),
                "Image_URL":  result["image_url"].split("/")[-1],
            }

            # усі пари header=value йдуть GET‑параметрами
            params = {"path": "Results", "action": "write", **row}
            print("⇢ sending GET → Sheets\n", json.dumps(params, indent=2, ensure_ascii=False))

            r = requests.get(SCRIPT_URL, params=params, timeout=10)
            print("⇠ Google Sheets status:", r.status_code, r.text[:120])
            r.raise_for_status()
            return r.text
        except Exception as e:
            return f"Error storing result: {e}"


    # (опційно) читання історії
    def get_user_results(self, username: str) -> list[dict]:
        data = self._get({"path": "Results", "action": "read"})
        if isinstance(data, dict) and "data" in data:
            return [r for r in data["data"] if r.get("Username") == username]
        return []
