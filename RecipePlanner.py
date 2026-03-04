import ast
import asyncio
import glob
import inspect
import os
import re
from typing import Any, List, Optional, Tuple, Union

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_embed, ollama_model_complete
from lightrag.utils import EmbeddingFunc


load_dotenv(dotenv_path=".env", override=False)


class RecipePlanner:
    """RAG-only helper for extracting ordered ingredient/action tuples from recipe texts."""

    def __init__(self, working_dir: str = "./graph", recipes_glob: str = "./recipes/*.txt"):
        self.working_dir = working_dir
        self.recipes_glob = recipes_glob
        os.makedirs(self.working_dir, exist_ok=True)
        self.rag: Optional[LightRAG] = None

    async def initialize_rag(self) -> LightRAG:
        rag = LightRAG(
            working_dir=self.working_dir,
            llm_model_func=ollama_model_complete,
            llm_model_name=os.getenv("LLM_MODEL", "deepseek-r1:8b"),
            summary_max_tokens=8192,
            llm_model_max_async=1,
            embedding_func_max_async=1,
            llm_model_kwargs={
                "host": os.getenv("LLM_BINDING_HOST", "http://localhost:11434"),
                "options": {"num_ctx": int(os.getenv("LLM_NUM_CTX", "20000"))},
                "timeout": int(os.getenv("TIMEOUT", "1200")),
            },
            embedding_func=EmbeddingFunc(
                embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
                max_token_size=int(os.getenv("MAX_EMBED_TOKENS", "8192")),
                func=lambda texts: ollama_embed(
                    texts,
                    embed_model=os.getenv("EMBEDDING_MODEL", "bge-m3:latest"),
                    host=os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434"),
                ),
            ),
        )

        await rag.initialize_storages()
        self.rag = rag
        return rag

    async def ingest_recipes(self) -> int:
        if self.rag is None:
            await self.initialize_rag()

        assert self.rag is not None
        file_paths = glob.glob(self.recipes_glob)
        texts = []

        for path in file_paths:
            with open(path, "r", encoding="utf-8") as file:
                texts.append(file.read())

        if texts:
            await self.rag.ainsert(texts, file_paths=file_paths, ids=file_paths)

        return len(texts)

    @staticmethod
    def _instruction_prompt() -> str:
        return (
            "You are a helper for recipes. For any requested recipe, return all ingredients and "
            "the action required to prepare them in the order they appear. "
            "Use EXACT tuples like ('cucumber','Dicing'). "
            "For mixing/grouping/addition steps that combine multiple items, use ((ing1, ing2, ...), 'Mixing'). "
            "Only use actions from: 'Carving','Chopping','Cubing','Cutting','Dicing','Halving','Julienning',"
            "'Mincing','Paring','Quartering','Slicing','Mixing'. "
            "Return a Python list and nothing else."
        )

    @staticmethod
    def parse_ingredient_actions(response_text: str) -> List[Union[Tuple[str, str], Tuple[Tuple[str, ...], str]]]:
        list_patterns = []
        depth = 0
        start_idx = None

        for i, char in enumerate(response_text):
            if char == "[":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0 and start_idx is not None:
                    list_patterns.append(response_text[start_idx : i + 1])
                    start_idx = None

        parsed_list: Optional[List[Any]] = None

        for pattern in list_patterns:
            try:
                parsed = ast.literal_eval(pattern)
                if isinstance(parsed, list):
                    parsed_list = parsed
                    break
            except (ValueError, SyntaxError):
                continue

        if parsed_list is None:
            cleaned = response_text.strip()
            cleaned = re.sub(r"^```(?:python|py)?\\s*\\n?", "", cleaned)
            cleaned = re.sub(r"\\n?```\\s*$", "", cleaned)
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if match:
                parsed = ast.literal_eval(match.group(0))
                if isinstance(parsed, list):
                    parsed_list = parsed

        if parsed_list is None:
            raise ValueError("No valid Python list found in model response")

        return parsed_list

    async def extract_ingredient_actions(self, recipe_query: str) -> List[Any]:
        if self.rag is None:
            await self.initialize_rag()

        assert self.rag is not None

        query_param = QueryParam(
            mode="hybrid",
            response_type="Single Paragraph",
            stream=False,
            enable_rerank=False,
            include_references=False,
        )

        response = await self.rag.aquery(
            f"{self._instruction_prompt()}\n\nQuery: {recipe_query}",
            param=query_param,
        )

        if inspect.isasyncgen(response):
            chunks = []
            async for chunk in response:
                chunks.append(str(chunk))
            response_text = "".join(chunks)
        else:
            response_text = str(response)

        return self.parse_ingredient_actions(response_text)


async def main() -> None:
    planner = RecipePlanner()
    try:
        await planner.initialize_rag()
        loaded = await planner.ingest_recipes()
        print(f"Loaded {loaded} recipe text files into graph")

        recipe_name = "Apple Almond Honey Mix"
        result = await planner.extract_ingredient_actions(f"{recipe_name}, please.")

        print("\nExtracted ingredient/action tuples:")
        for item in result:
            print(item)
    finally:
        if planner.rag is not None:
            await planner.rag.llm_response_cache.index_done_callback()
            await planner.rag.finalize_storages()


if __name__ == "__main__":
    asyncio.run(main())
