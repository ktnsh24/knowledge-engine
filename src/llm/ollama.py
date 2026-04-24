"""Ollama LLM — local provider, free, no internet required."""
import json
import httpx
from src.llm.base import BaseLLM, DONKEY_SYSTEM_PROMPT
from src.config import get_settings


class OllamaLLM(BaseLLM):

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_llm_model

    async def complete(self, question: str, context: str,
                       system_prompt: str = DONKEY_SYSTEM_PROMPT,
                       temperature: float = 0.1) -> str:
        prompt = f"{system_prompt}\n\n---CONTEXT---\n{context}\n\n---QUESTION---\n{question}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt,
                      "stream": False, "options": {"temperature": temperature}},
            )
            resp.raise_for_status()
            return resp.json()["response"]

    async def extract_topics_and_relations(self, text: str) -> dict:
        prompt = f"""Extract topics and relationships from this text.
Return JSON only, no explanation:
{{
  "topics": [{{"id": "slug-name", "name": "Human Name", "description": "1 sentence"}}],
  "relationships": [{{"source_id": "...", "target_id": "...", "relation_type": "USED_BY|STORED_IN|REQUIRED_BY|PART_OF|RELATED_TO", "evidence": "sentence"}}]
}}

TEXT:
{text[:3000]}"""
        result = await self.complete(prompt, "", system_prompt="You extract structured data. Return JSON only.")
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            return json.loads(result[start:end])
        except Exception:
            return {"topics": [], "relationships": []}

    async def generate_wiki_page(self, topic_name: str, context: str) -> dict:
        prompt = f"""Write a wiki page for the topic: "{topic_name}"

Use the context below. Include:
1. 🫏 Donkey analogy (required)
2. What it is (definition)
3. How it works (technical)
4. Why it matters (real-world scenario)
5. Connected concepts

CONTEXT:
{context[:4000]}"""
        content = await self.complete(prompt, context)
        donkey_start = content.find("🫏")
        donkey_end = content.find("\n", donkey_start + 1) if donkey_start != -1 else -1
        donkey = content[donkey_start:donkey_end].strip() if donkey_start != -1 else ""
        return {"content": content, "donkey_analogy": donkey}
