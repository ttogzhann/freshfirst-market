"""Isolated real HTTP server for the frontend integration suite; never production seed data."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn

from app.main import create_app
from app.services.fresh import FreshService


class Source:
    def meals(self):
        return iter(
            [
                {
                    "idMeal": "integration",
                    "strMeal": "Integration pasta",
                    "strCategory": "Pasta",
                    "strInstructions": "Cook the measured ingredients.",
                    "strMealThumb": "https://www.themealdb.com/images/test.jpg",
                    "strIngredient1": "Pasta",
                    "strMeasure1": "100g",
                    "strIngredient2": "Milk",
                    "strMeasure2": "100ml",
                    "strIngredient3": "Butter",
                    "strMeasure3": "10g",
                }
            ]
        )


if __name__ == "__main__":
    service = FreshService(source=Source(), seed=False, today=lambda: date(2026, 10, 20))
    service.import_recipes()
    uvicorn.run(
        create_app(service, startup_import=False),
        host="127.0.0.1",
        port=int(sys.argv[1]),
        log_level="warning",
    )
