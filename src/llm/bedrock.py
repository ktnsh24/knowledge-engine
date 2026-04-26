"""AWS Bedrock LLM — uses Converse API, same pattern as rag-chatbot."""
import json
import boto3
from src.llm.base import BaseLLM, COURIER_SYSTEM_PROMPT
from src.config import get_settings


class BedrockLLM(BaseLLM):

    def __init__(self):
        settings = get_settings()
        self.model_id = settings.aws_bedrock_llm_model
        self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    async def complete(self, question: str, context: str,
                       system_prompt: str = COURIER_SYSTEM_PROMPT,
                       temperature: float = 0.1) -> str:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_complete, question, context, system_prompt, temperature
        )

    def _sync_complete(self, question: str, context: str,
                       system_prompt: str, temperature: float) -> str:
        user_content = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_content}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": 2048},
        )
        return response["output"]["message"]["content"][0]["text"]

    async def extract_topics_and_relations(self, text: str) -> dict:
        prompt = f"""Extract topics and relationships. Return JSON only:
{{"topics": [{{"id": "slug", "name": "Name", "description": "1 sentence"}}],
 "relationships": [{{"source_id": "...", "target_id": "...", "relation_type": "USED_BY", "evidence": "..."}}]}}

TEXT: {text[:3000]}"""
        result = await self.complete(prompt, "", system_prompt="Return JSON only, no explanation.")
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            return json.loads(result[start:end])
        except Exception:
            return {"topics": [], "relationships": []}

    async def generate_wiki_page(self, topic_name: str, context: str) -> dict:
        prompt = f"""Write a wiki page for: "{topic_name}"
Include: 🚚 courier analogy, definition, how it works, why it matters, connected concepts.
CONTEXT: {context[:4000]}"""
        content = await self.complete(prompt, context)
        courier_start = content.find("🚚")
        courier_end = content.find("\n", courier_start + 1) if courier_start != -1 else -1
        courier = content[courier_start:courier_end].strip() if courier_start != -1 else ""
        return {"content": content, "courier_analogy": courier}
