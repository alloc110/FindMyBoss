import json
import time
from typing import Any, Dict, Optional
import httpx

from config import get_logger
from models.schemas import GeminiTailorResponse
from services.ai.base import BaseAIProvider, build_tailor_prompt

logger = get_logger("OpenAIProvider")


class OpenAIProvider(BaseAIProvider):
    """OpenAI (ChatGPT) AI Provider."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini", base_url: Optional[str] = None):
        super().__init__(api_key=api_key, model_name=model_name or "gpt-4o-mini", base_url=base_url)

    def test_connection(self, api_key: str, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name or "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(url, headers=headers, json=payload)
            latency_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                return {
                    "ok": True,
                    "success": True,
                    "provider": "OpenAI (ChatGPT)",
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "message": f"Kết nối OpenAI thành công ({latency_ms}ms)! Mô hình {model_name} sẵn sàng.",
                }
            else:
                err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_json.get("error", {}).get("message", resp.text)
                msg = f"Lỗi OpenAI ({resp.status_code}): {err_msg}"
                return {
                    "ok": False,
                    "success": False,
                    "provider": "OpenAI (ChatGPT)",
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "message": msg,
                    "error": msg,
                    "status_code": resp.status_code,
                }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            msg = f"Lỗi kết nối mạng hoặc timeout: {str(e)}"
            return {
                "ok": False,
                "success": False,
                "latency_ms": latency_ms,
                "message": msg,
                "error": msg,
                "provider": "OpenAI (ChatGPT)",
                "model": model_name,
            }

    def tailor_cv(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        prompt = build_tailor_prompt(job, profile)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name or "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an elite Tech Recruiter and ATS Resume Specialist. Output valid JSON strictly matching the requested schema without any markdown formatting.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        with httpx.Client(timeout=35.0) as client:
            res = client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return GeminiTailorResponse(**parsed)
