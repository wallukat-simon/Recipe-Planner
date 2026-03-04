import asyncio
import json
import os
from pathlib import Path

from RecipePlanner import RecipePlanner
from queryMeals import MealPlanner


async def run_pipeline(recipe_query: str) -> list:
    planner = RecipePlanner(
        working_dir=os.getenv("WORKING_DIR", "./graph"),
        recipes_glob=os.getenv("RECIPES_GLOB", "./recipes/*.txt"),
    )
    meal_planner = MealPlanner()

    try:
        await planner.initialize_rag()
        loaded = await planner.ingest_recipes()
        print(f"Loaded {loaded} recipe files into graph")

        tuples = await planner.extract_ingredient_actions(recipe_query)
        print(f"Extracted {len(tuples)} ingredient/action items")

        plans = []
        for item in tuples:
            if isinstance(item, tuple) and len(item) == 2:
                ingredient, action = item
                plan = meal_planner.generate_plan(ingredient, action)
                plans.append(plan)
                meal_planner.queryer.print_plan(plan)

        output_dir = Path(os.getenv("RESULTS_DIR", "./results"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "latest_plans.json"
        with Path.open(output_path, "w", encoding="utf-8") as file:
            json.dump(plans, file, indent=2, ensure_ascii=False)
        print(f"Saved plans to {output_path}")
        return plans
    finally:
        if planner.rag is not None:
            await planner.rag.llm_response_cache.index_done_callback()
            await planner.rag.finalize_storages()


def main() -> None:
    recipe_query = os.getenv("RECIPE_QUERY", "Apple Almond Honey Mix, please.")
    asyncio.run(run_pipeline(recipe_query))


if __name__ == "__main__":
    main()
