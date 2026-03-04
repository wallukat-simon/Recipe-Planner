#!/usr/bin/env python3
"""
Meal ontology querying utilities.

This module is intentionally OEO-free and focused on the MealPreparation endpoint.
It provides:
- OntologyQueryer: low-level SPARQL access + task/food property retrieval
- MealPlanner: high-level ingredient/action -> execution plan helper
"""

import re
from typing import Dict, List, Optional, Union

import requests


class OntologyQueryer:
    OWL_PREFIX = "http://www.w3.org/2002/07/owl#"
    MEALS_PREFIX = "http://www.ease-crc.org/ont/meals#"
    RDF_PREFIX = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    RDFS_PREFIX = "http://www.w3.org/2000/01/rdf-schema#"
    FOODON_PREFIX = "http://purl.obolibrary.org/obo/"
    SOMA_PREFIX = "http://www.ease-crc.org/ont/SOMA.owl#"
    SIT_AWARE_PREFIX = "http://www.ease-crc.org/ont/situation_awareness#"

    ENDPOINT_URL = "https://knowledgedb.informatik.uni-bremen.de/mealprepDB/MealPreparation/query"

    def __init__(self, endpoint_url: Optional[str] = None):
        if endpoint_url:
            self.ENDPOINT_URL = endpoint_url

    def _query_sparql(self, sparql_query: str, query_type: str = "SELECT") -> Dict:
        headers = {"Content-Type": "application/sparql-query"}
        try:
            response = requests.post(
                self.ENDPOINT_URL,
                data=sparql_query,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            print(f"Error querying endpoint ({query_type}): {error}")
            return {}

    def _query_text(self, sparql_query: str, fallback: str) -> str:
        result = self._query_sparql(sparql_query, "SELECT")
        try:
            value = (
                result.get("results", {})
                .get("bindings", [{}])[0]
                .get("res", {})
                .get("value", "")
            )
            return value if value else fallback
        except (IndexError, KeyError):
            return fallback

    def _extract_name(self, uri: str) -> str:
        return re.sub(r"^.*[#/]", "", uri)

    def check_food_part(self, food: str, part: str) -> bool:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdf: <{self.RDF_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            PREFIX foodon: <{self.FOODON_PREFIX}>
            ASK {{
              foodon:{food} rdfs:subClassOf* ?dis.
              ?dis owl:onProperty meals:hasPart.
              ?dis owl:someValuesFrom ?tar.
              ?tar owl:intersectionOf ?tar_int.
              ?tar_int rdf:first meals:{part}.
              ?tar_int rdf:rest ?rest.
              ?rest rdf:first ?first.
              ?first owl:onProperty meals:hasEdibility.
              {{ ?first owl:someValuesFrom meals:MustBeAvoided. }}
              UNION
              {{ ?first owl:someValuesFrom meals:ShouldBeAvoided. }}
            }}
        """
        result = self._query_sparql(sparql_query, "ASK")
        return result.get("boolean", False)

    def get_prior_task(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            SELECT ?res WHERE {{
                {verb} rdfs:subClassOf* ?sub.
                ?sub owl:onProperty meals:requiresPriorTask.
                ?sub owl:someValuesFrom ?priortask.
                BIND(REPLACE(STR(?priortask), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "")

    def get_peel_tool(self, food: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX soma: <{self.SOMA_PREFIX}>
            PREFIX rdf: <{self.RDF_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            PREFIX foodon: <{self.FOODON_PREFIX}>
            SELECT ?res WHERE {{
                foodon:{food} rdfs:subClassOf* ?peel_dis.
                ?peel_dis owl:onProperty soma:hasDisposition.
                ?peel_dis owl:someValuesFrom ?peel_dis_vals.
                ?peel_dis_vals owl:intersectionOf ?afford_vals.
                ?afford_vals rdf:first meals:Peelability.
                ?afford_vals rdf:rest ?task_trigger.
                ?task_trigger rdf:rest ?trigger.
                ?trigger rdf:first ?trigger_wo_nil.
                ?trigger_wo_nil owl:onProperty soma:affordsTrigger.
                ?trigger_wo_nil owl:allValuesFrom ?trigger_tool.
                ?trigger_tool owl:allValuesFrom ?tool.
                BIND(REPLACE(STR(?tool), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "Peeler")

    def get_cut_tool(self, food: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX soma: <{self.SOMA_PREFIX}>
            PREFIX rdf: <{self.RDF_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            PREFIX foodon: <{self.FOODON_PREFIX}>
            PREFIX sit_aware: <{self.SIT_AWARE_PREFIX}>
            SELECT ?res WHERE {{
                foodon:{food} rdfs:subClassOf* ?cut_dis.
                ?cut_dis owl:onProperty soma:hasDisposition.
                ?cut_dis owl:someValuesFrom ?cut_dis_vals.
                ?cut_dis_vals owl:intersectionOf ?afford_vals.
                ?afford_vals rdf:first sit_aware:Cuttability.
                ?afford_vals rdf:rest ?task_trigger.
                ?task_trigger rdf:rest ?trigger.
                ?trigger rdf:first ?trigger_wo_nil.
                ?trigger_wo_nil owl:onProperty soma:affordsTrigger.
                ?trigger_wo_nil owl:allValuesFrom ?trigger_tool.
                ?trigger_tool owl:allValuesFrom ?tool.
                BIND(REPLACE(STR(?tool), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "Knife")

    def get_target(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdf: <{self.RDF_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            SELECT ?res WHERE {{
              {{
                {verb} rdfs:subClassOf* ?inter_node.
                ?inter_node owl:intersectionOf ?in_res_node.
                ?in_res_node rdf:first ?input_node.
                ?input_node owl:onProperty meals:hasInputObject.
                ?input_node owl:someValuesFrom ?target.
                FILTER NOT EXISTS {{ ?target owl:unionOf ?union_node. }}
                BIND(REPLACE(STR(?target), "^.*[#/]", "") AS ?res).
              }}
              UNION
              {{
                {verb} rdfs:subClassOf* ?inter_node.
                ?inter_node owl:intersectionOf ?in_res_node.
                ?in_res_node rdf:first ?input_node.
                ?input_node owl:onProperty meals:hasInputObject.
                ?input_node owl:someValuesFrom ?targets_node.
                ?targets_node owl:unionOf ?union_node.
                ?union_node rdf:first ?target.
                BIND(REPLACE(STR(?target), "^.*[#/]", "") AS ?res).
              }}
            }}
        """
        return self._query_text(sparql_query, "Food")

    def get_repetitions(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            SELECT ?res WHERE {{
              {{
                {verb} rdfs:subClassOf* ?rep_node.
                ?rep_node owl:onProperty meals:repetitions.
                FILTER EXISTS {{ ?rep_node owl:hasValue ?val. }}
                BIND("exactly 1" AS ?res)
              }}
              UNION
              {{
                {verb} rdfs:subClassOf* ?rep_node.
                ?rep_node owl:onProperty meals:repetitions.
                FILTER EXISTS {{ ?rep_node owl:minQualifiedCardinality ?val. }}
                BIND("at least 1" AS ?res)
              }}
            }}
        """
        return self._query_text(sparql_query, "1")

    def get_cutting_position(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            SELECT ?res WHERE {{
                {verb} rdfs:subClassOf* ?pos_node.
                ?pos_node owl:onProperty meals:affordsPosition.
                ?pos_node owl:someValuesFrom ?pos.
                BIND(REPLACE(STR(?pos), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "middle")

    def get_mixing_motion(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            PREFIX owl: <{self.OWL_PREFIX}>
            SELECT ?res WHERE {{
                {verb} rdfs:subClassOf* ?node.
                ?node owl:onProperty meals:requiresMotion.
                ?node owl:someValuesFrom ?motion.
                BIND(REPLACE(STR(?motion), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "")

    def get_mixing_tool(self, verb: str) -> str:
        sparql_query = f"""
            PREFIX owl: <{self.OWL_PREFIX}>
            PREFIX soma: <{self.SOMA_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            SELECT ?res WHERE {{
                {verb} rdfs:subClassOf* ?node.
                ?node owl:onProperty soma:affordsTrigger.
                ?node owl:someValuesFrom ?tool.
                BIND(REPLACE(STR(?tool), "^.*[#/]", "") AS ?res).
            }}
        """
        return self._query_text(sparql_query, "")

    def get_min_inputs(self, verb: str) -> int:
        sparql_query = f"""
            PREFIX meals: <{self.MEALS_PREFIX}>
            PREFIX rdfs: <{self.RDFS_PREFIX}>
            PREFIX owl: <{self.OWL_PREFIX}>
            SELECT ?min WHERE {{
                {verb} rdfs:subClassOf* ?node.
                ?node owl:onProperty meals:hasInputObject.
                ?node owl:minQualifiedCardinality ?min.
            }}
        """
        result = self._query_sparql(sparql_query, "SELECT")
        try:
            min_value = (
                result.get("results", {})
                .get("bindings", [{}])[0]
                .get("min", {})
                .get("value", "")
            )
            return int(min_value) if min_value else 1
        except (IndexError, KeyError, ValueError):
            return 1

    def query_and_show(self, food: Union[str, List[str]], task: str) -> Dict:
        if isinstance(food, list):
            food_display = ", ".join(food)
        else:
            food_display = food

        mixing_tasks = {"Adding", "Beating", "Folding", "Grouping", "Mixing", "Whisking"}
        task_name = task.split(":")[-1] if ":" in task else task
        is_mixing_task = task_name in mixing_tasks

        if is_mixing_task:
            mixing_tool = self.get_mixing_tool(task)
            motion = self.get_mixing_motion(task)
            min_inputs = self.get_min_inputs(task)
            cut_tool = None
            reps = None
            pos = None
            peel_tool = None
        else:
            remove_peel = self.check_food_part(food, "Peel")
            remove_shell = self.check_food_part(food, "Shell")
            remove_stem = self.check_food_part(food, "Stem")
            remove_core = self.check_food_part(food, "Core")
            prior_task = self.get_prior_task(task)
            peel_tool = self.get_peel_tool(food)
            cut_tool = self.get_cut_tool(food)
            reps = self.get_repetitions(task)
            pos = self.get_cutting_position(task)
            shape = self.get_target(task)
            mixing_tool = None
            motion = None
            min_inputs = None

        steps = []
        curr_step = 1

        if not is_mixing_task:
            if remove_peel or remove_shell:
                steps.append(
                    {
                        "step": curr_step,
                        "motion": "Peeling using a peeling tool",
                        "inference": f"peeling tool = {peel_tool}",
                    }
                )
                curr_step += 1

            if remove_stem:
                steps.append(
                    {
                        "step": curr_step,
                        "motion": "Removing the stem",
                        "inference": "has stem = true",
                    }
                )
                curr_step += 1

            if remove_core:
                steps.append(
                    {
                        "step": curr_step,
                        "motion": "Removing the core",
                        "inference": "has core = true",
                    }
                )
                curr_step += 1

            if prior_task:
                steps.append(
                    {
                        "step": curr_step,
                        "motion": f"Execute prior task: {prior_task}",
                        "inference": f"prior task = {prior_task}",
                    }
                )
                curr_step += 1

        if is_mixing_task:
            tool = mixing_tool if mixing_tool else "mixing tool"
            motion_desc = motion if motion else "mixing"
            steps.extend(
                [
                    {
                        "step": curr_step,
                        "motion": f"Pick up the {tool}",
                        "inference": f"mixing tool = {tool}",
                    },
                    {
                        "step": curr_step + 1,
                        "motion": f"Perform {motion_desc} on ingredients",
                        "inference": f"motion = {motion_desc}; min inputs = {min_inputs}; target = {food_display}",
                    },
                    {
                        "step": curr_step + 2,
                        "motion": f"Place down the {tool}",
                        "inference": f"mixing tool = {tool}",
                    },
                ]
            )
        else:
            target = food if shape == "Food" else f"{food} {shape}"
            steps.extend(
                [
                    {
                        "step": curr_step,
                        "motion": "Pick up the cutting tool",
                        "inference": f"cutting tool = {cut_tool}",
                    },
                    {
                        "step": curr_step + 1,
                        "motion": "Cut the target object",
                        "inference": f"target = {target}; position = {pos}; repetitions = {reps}",
                    },
                    {
                        "step": curr_step + 2,
                        "motion": "Place down the cutting tool",
                        "inference": f"cutting tool = {cut_tool}",
                    },
                ]
            )

        plan = {
            "task": task,
            "food": food_display,
            "steps": steps,
            "peel_tool": peel_tool,
        }

        if is_mixing_task:
            plan["mixing_tool"] = mixing_tool
            plan["motion"] = motion
            plan["min_inputs"] = min_inputs
        else:
            plan["cutting_tool"] = cut_tool
            plan["position"] = pos
            plan["repetitions"] = reps

        return plan

    def print_plan(self, plan: Dict) -> None:
        print("\n" + "=" * 80)
        task_name = plan["task"].split(":")[-1] if ":" in plan["task"] else plan["task"]
        print(f"Plan for {task_name} on {plan['food']}")
        print("=" * 80)
        for step in plan["steps"]:
            print(f"Step {step['step']}: {step['motion']}")
            if step["inference"]:
                print(f"  -> {step['inference']}")


class MealPlanner:
    """High-level wrapper that resolves ingredient/action strings and generates plans."""

    ACTION_TO_TASK = {
        "carving": "meals:Carving",
        "chopping": "meals:Chopping",
        "cubing": "meals:Cubing",
        "cutting": "soma:Cutting",
        "dicing": "soma:Dicing",
        "halving": "meals:Halving",
        "julienning": "meals:Julienning",
        "mincing": "meals:Mincing",
        "paring": "meals:Paring",
        "quartering": "meals:Quartering",
        "slicing": "soma:Slicing",
        "adding": "meals:Adding",
        "beating": "meals:Beating",
        "folding": "meals:Folding",
        "grouping": "meals:Grouping",
        "mixing": "meals:Mixing",
        "whisking": "meals:Whisking",
    }

    FOOD_NAME_TO_ID = {
        "almond": "FOODON_00003523",
        "apple": "FOODON_03301710",
        "avocado": "FOODON_00003600",
        "banana": "FOODON_00004183",
        "chocolate": "FOODON_03307240",
        "cucumber": "FOODON_00003415",
        "honey": "FOODON_00001178",
        "milk": "UBERON_0001913",
        "olive": "FOODON_03317509",
        "peach": "FOODON_03315502",
        "pineapple": "FOODON_00003459",
        "strawberry": "FOODON_00003443",
        "sugar": "FOODON_03301073",
        "syrup": "FOODON_03303225",
        "tomato": "FOODON_03309927",
        "vinegar": "FOODON_03301705",
        "cream": "cream",
    }

    def __init__(self, queryer: Optional[OntologyQueryer] = None):
        self.queryer = queryer or OntologyQueryer()

    def _resolve_ingredient(self, ingredient: str) -> str:
        key = ingredient.lower().strip()
        return self.FOOD_NAME_TO_ID.get(key, ingredient)

    def generate_plan(self, ingredient: Union[str, List[str], tuple], action: str) -> Dict:
        task = self.ACTION_TO_TASK.get(action.lower(), action)

        if isinstance(ingredient, (list, tuple)):
            resolved_food = [self._resolve_ingredient(item) for item in ingredient]
            food_for_query: Union[str, List[str]] = resolved_food
            food_display = ", ".join(str(item) for item in ingredient)
        else:
            food_for_query = self._resolve_ingredient(ingredient)
            food_display = ingredient

        plan = self.queryer.query_and_show(food_for_query, task)
        plan["food"] = food_display
        return plan
