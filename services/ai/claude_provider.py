import json
import time
from typing import Any, Dict, Optional
import httpx

from config import get_logger
from models.schemas import GeminiTailorResponse
from services.ai.base import BaseAIProvider, build_tailor_prompt, extract_json_block

logger = get_logger("ClaudeProvider")


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude AI Provider."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "claude-3-5-sonnet-20241022", base_url: Optional[str] = None):
        super().__init__(api_key=api_key, model_name=model_name or "claude-3-5-sonnet-20241022", base_url=base_url)

    def test_connection(self, api_key: str, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name or "claude-3-5-haiku-20241022",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "Hi"}],
        }

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(url, headers=headers, json=payload)
            latency_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                return {
                    "ok": True,
                    "success": True,
                    "provider": "Anthropic Claude",
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "message": f"Kết nối Claude thành công ({latency_ms}ms)! Mô hình {model_name} sẵn sàng.",
                }
            else:
                err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_json.get("error", {}).get("message", resp.text)
                msg = f"Lỗi Claude ({resp.status_code}): {err_msg}"
                return {
                    "ok": False,
                    "success": False,
                    "provider": "Anthropic Claude",
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
                "provider": "Anthropic Claude",
                "model": model_name,
            }

    def tailor_cv(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        prompt = build_tailor_prompt(job, profile)
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name or "claude-3-5-sonnet-20241022",
            "max_tokens": 2500,
            "system": "You are an elite Tech Recruiter and ATS Resume Specialist. Always respond strictly with valid JSON without any markdown formatting.",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=35.0) as client:
            res = client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        raw_text = res.json()["content"][0]["text"]
        clean_json = extract_json_block(raw_text)
        parsed = json.loads(clean_json)
        return GeminiTailorResponse(**parsed)
