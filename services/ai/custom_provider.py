import json
import time
from typing import Any, Dict, Optional
import httpx

from config import get_logger
from models.schemas import GeminiTailorResponse
from services.ai.base import BaseAIProvider, build_tailor_prompt, extract_json_block

logger = get_logger("CustomAIProvider")


class CustomProvider(BaseAIProvider):
    """Custom OpenAI-compatible provider (DeepSeek, Ollama, OpenRouter, vLLM)."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "deepseek-chat", base_url: Optional[str] = None):
        super().__init__(api_key=api_key, model_name=model_name or "deepseek-chat", base_url=base_url)

    def test_connection(self, api_key: str, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        root_url = (base_url or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{root_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name or "deepseek-chat",
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
                    "provider": "DeepSeek / Custom",
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "message": f"Kết nối tùy chỉnh thành công ({latency_ms}ms)! Endpoint {url} phản hồi tốt.",
                }
            else:
                err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_json.get("error", {}).get("message", resp.text)
                msg = f"Lỗi Custom API ({resp.status_code}): {err_msg}"
                return {
                    "ok": False,
                    "success": False,
                    "provider": "DeepSeek / Custom",
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
                "provider": "DeepSeek / Custom",
                "model": model_name,
            }

    def tailor_cv(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        prompt = build_tailor_prompt(job, profile)
        root_url = (self.base_url or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{root_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name or "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an elite Tech Recruiter and ATS Resume Specialist. Output valid JSON strictly.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        with httpx.Client(timeout=40.0) as client:
            res = client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        clean_json = extract_json_block(content)
        parsed = json.loads(clean_json)
        return GeminiTailorResponse(**parsed)
