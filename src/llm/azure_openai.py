"""Azure OpenAI LLM."""
import json
from openai import AsyncAzureOpenAI
from src.llm.base import BaseLLM, DONKEY_SYSTEM_PROMPT
from src.config import get_settings


class AzureOpenAILLM(BaseLLM):

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_llm_deployment

    async def complete(self, question: str, context: str,
                       system_prompt: str = DONKEY_SYSTEM_PROMPT,
                       temperature: float = 0.1) -> str:
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    async def extract_topics_and_relations(self, text: str) -> dict:
        prompt = f"""Extract topics and relationships. Return JSON only:
{{"topics": [{{"id": "slug", "name": "Name", "description": "1 sentence"}}],
 "relationships": [{{"source_id": "...", "target_id": "...", "relation_type": "USED_BY", "evidence": "..."}}]}}

TEXT: {text[:3000]}"""
        result = await self.complete(prompt, "", system_prompt="Return JSON only.")
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            return json.loads(result[start:end])
        except Exception:
            return {"topics": [], "relationships": []}

    async def generate_wiki_page(self, topic_name: str, context: str) -> dict:
        prompt = f"""Write a wiki page for: "{topic_name}"
Include: 🫏 donkey analogy, definition, how it works, why it matters, connected concepts.
CONTEXT: {context[:4000]}"""
        content = await self.complete(prompt, context)
        donkey_start = content.find("🫏")
        donkey_end = content.find("\n", donkey_start + 1) if donkey_start != -1 else -1
        donkey = content[donkey_start:donkey_end].strip() if donkey_start != -1 else ""
        return {"content": content, "donkey_analogy": donkey}
