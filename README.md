# Recipe-Planner

Recipe-Planner is a LightRAG-based pipeline focused on recipe understanding and meal-task planning.

## What it does

1. Ingests recipe text files from `recipes/` into a LightRAG graph (`graph/`).
2. Extracts ordered `(ingredient, action)` tuples for a requested recipe.
3. Resolves each tuple against the meal ontology endpoint and generates executable preparation plans.
4. Writes the generated plans to `results/latest_plans.json`.

## Core files

- `RecipePlanner.py`: RAG ingestion and ingredient/action extraction.
- `queryMeals.py`: ontology querying and plan generation.
- `main.py`: end-to-end pipeline runner.

## Run locally

1. Install dependencies:
	- `pip install -r requirements.txt`
2. Ensure Ollama is running and accessible.
3. Run the pipeline:
	- `python main.py`

Optional environment variables:

- `LLM_BINDING_HOST` (default: `http://localhost:11434`)
- `EMBEDDING_BINDING_HOST` (default: `http://localhost:11434`)
- `LLM_MODEL`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIM`
- `WORKING_DIR` (default: `./graph`)
- `RECIPES_GLOB` (default: `./recipes/*.txt`)
- `RESULTS_DIR` (default: `./results`)
- `RECIPE_QUERY` (default: `Apple Almond Honey Mix, please.`)
