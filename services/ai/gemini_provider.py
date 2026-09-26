import time
from typing import Any, Dict, Optional
import httpx

from config import get_logger
from models.schemas import GeminiTailorResponse
from services.ai.base import BaseAIProvider, build_tailor_prompt, clean_and_parse_json

logger = get_logger("GeminiProvider")


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI Provider."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash", base_url: Optional[str] = None):
        super().__init__(api_key=api_key, model_name=model_name, base_url=base_url)
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini API initialized successfully with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize official google-genai client: {e}")
                self._client = None
        else:
            self._client = None

    def test_connection(self, api_key: str, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Reply with 'OK' in 1 word."}]}],
            "generationConfig": {"maxOutputTokens": 5},
        }

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(url, json=payload)
            latency_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                return {
                    "ok": True,
                    "success": True,
                    "provider": "Google Gemini",
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "message": f"Kết nối Gemini thành công ({latency_ms}ms)! Mô hình {model_name} sẵn sàng.",
                }
            else:
                err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_json.get("error", {}).get("message", resp.text)
                msg = f"Lỗi Gemini ({resp.status_code}): {err_msg}"
                return {
                    "ok": False,
                    "success": False,
                    "provider": "Google Gemini",
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
                "provider": "Google Gemini",
                "model": model_name,
            }

    def tailor_cv(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        prompt = build_tailor_prompt(job, profile)

        if self._client:
            from google.genai import types
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=GeminiTailorResponse,
                        temperature=0.2,
                    ),
                )
                raw_text = response.text
            except Exception as client_err:
                logger.warning(f"Gemini client structured call failed ({client_err}), retrying with standard prompt...")
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt + "\n\nCRITICAL: Respond ONLY with a valid JSON object matching the requested schema. No code fences, no extra commentary.",
                )
                raw_text = response.text
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        parsed = clean_and_parse_json(raw_text)
        return GeminiTailorResponse(**parsed)
