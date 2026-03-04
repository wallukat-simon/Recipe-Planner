# How To Use

This workspace is centered around `RecipePlanner.py` and `queryMeals.py`.

## Local run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start Ollama locally.
3. Run:
   - `python main.py`

## Inputs

- Recipe text files in `recipes/`
- Query string from env var `RECIPE_QUERY`

## Outputs

- LightRAG graph data in `graph/`
- Generated plans in `results/latest_plans.json`

## Docker run

1. Build and run:
   - `docker compose up --build`
2. Configure runtime with these environment variables in `docker-compose.yml`:
   - `LLM_BINDING_HOST`
   - `EMBEDDING_BINDING_HOST`
   - `LLM_MODEL`
   - `EMBEDDING_MODEL`
   - `EMBEDDING_DIM`
   - `WORKING_DIR`
   - `RECIPES_GLOB`
   - `RESULTS_DIR`
   - `RECIPE_QUERY`