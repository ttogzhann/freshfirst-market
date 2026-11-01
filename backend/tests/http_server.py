"""Isolated real HTTP server for the frontend integration suite; never production seed data."""

import os
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FRESHFIRST_AUTH_SECRET", "isolated frontend HTTP test secret 32 bytes")
import uvicorn

with patch.dict(
    os.environ,
    {
        "DATABASE_URL": "sqlite:///:memory:",
        "FRESHFIRST_AUTH_SECRET": "isolated frontend HTTP test secret 32 bytes",
    },
):
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
    with TemporaryDirectory(prefix="freshfirst-http-") as directory:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(directory) / 'http.db'}"
        service = FreshService(source=Source(), seed=False, today=lambda: date(2026, 10, 20))
        service.import_recipes()
        try:
            uvicorn.run(
                create_app(service, startup_import=False),
                host="127.0.0.1",
                port=int(sys.argv[1]),
                log_level="warning",
            )
        finally:
            service.store.close()
