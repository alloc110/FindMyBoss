import json
import os
import re
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from config import get_logger

logger = get_logger("AIService")


class GeminiTailorResponse(BaseModel):
    match_score: int = Field(default=80, description="Percentage match between candidate and JD (0-100)")
    match_analysis: str = Field(default="", description="Brief assessment of strengths and gaps")
    missing_skills: List[str] = Field(default_factory=list, description="High-priority ATS skills present in JD but missing in candidate profile")
    tailored_summary: str = Field(default="", description="Tailored 3-4 sentence professional summary targeting this specific job")
    tailored_bullets: List[str] = Field(default_factory=list, description="3-4 tailored experience bullets in STAR/XYZ format emphasizing JD tech stack")


class MultiProviderAIService:
    """
    Multi-Provider AI Service supporting Google Gemini, OpenAI (ChatGPT),
    Anthropic (Claude), and OpenAI-compatible endpoints (DeepSeek, Ollama, OpenRouter).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        provider: str = "gemini",
        base_url: Optional[str] = None,
    ):
        self.provider = (provider or "gemini").lower().strip()
        self.model_name = model_name or "gemini-2.5-flash"
        self.api_key = api_key if api_key is not None else self._get_env_key_for_provider(self.provider)
        self.base_url = (base_url or "").strip() or None
        self._client = None
        self._init_client()

    def _get_env_key_for_provider(self, provider: str) -> Optional[str]:
        if provider == "gemini":
            return os.getenv("GEMINI_API_KEY")
        elif provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        elif provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY")
        elif provider == "custom":
            return os.getenv("CUSTOM_AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        return None

    def _init_client(self):
        if self.provider == "gemini" and self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini API initialized successfully with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize official google-genai client: {e}")
                self._client = None
        elif self.api_key:
            logger.info(f"AI Service configured for provider: {self.provider}, model: {self.model_name}")
        else:
            self._client = None
            logger.warning(f"API Key for {self.provider} not set. AIService will run in fallback simulation mode until key is provided.")

    def configure(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Dynamically reconfigures provider, API key, model, and base URL."""
        if provider:
            self.provider = provider.lower().strip()
        if api_key is not None:
            self.api_key = api_key.strip() or None
        if model_name:
            self.model_name = model_name.strip()
        if base_url is not None:
            self.base_url = base_url.strip() or None
        self._init_client()

    def test_connection(
        self,
        provider: str,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Actively tests whether the given provider, API key, and model can successfully connect.
        Returns latency in milliseconds and detailed status message.
        """
        provider = (provider or "gemini").lower().strip()
        api_key = (api_key or "").strip()
        model_name = (model_name or "").strip()
        base_url = (base_url or "").strip()

        if not api_key:
            return {
                "ok": False,
                "success": False,
                "latency_ms": 0,
                "message": "Vui lòng nhập API Key trước khi kiểm tra.",
                "error": "Vui lòng nhập API Key trước khi kiểm tra.",
                "provider": provider,
                "model": model_name,
            }

        start_time = time.time()

        try:
            if provider == "gemini":
                # Test Google Gemini endpoint
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": "Reply with 'OK' in 1 word."}]}],
                    "generationConfig": {"maxOutputTokens": 5},
                }
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

            elif provider == "openai":
                # Test OpenAI endpoint
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

            elif provider == "claude":
                # Test Anthropic Claude endpoint
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

            elif provider == "custom":
                # Test Custom OpenAI-compatible endpoint (DeepSeek, Ollama, OpenRouter)
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

            return {
                "ok": False,
                "success": False,
                "latency_ms": 0,
                "message": f"Nhà cung cấp không hỗ trợ: {provider}",
                "error": f"Nhà cung cấp không hỗ trợ: {provider}",
                "provider": provider,
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
                "provider": provider,
                "model": model_name,
            }

    def tailor_cv_for_job(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """
        Analyzes the Job Description and candidate profile, returning structured
        tailoring recommendations (Match score, missing keywords, tailored summary & bullets).
        """
        if self.api_key:
            try:
                if self.provider == "gemini":
                    return self._call_gemini_api(job, profile)
                elif self.provider == "openai":
                    return self._call_openai_api(job, profile)
                elif self.provider == "claude":
                    return self._call_claude_api(job, profile)
                elif self.provider == "custom":
                    return self._call_custom_api(job, profile)
            except Exception as e:
                logger.error(f"{self.provider.upper()} API call failed: {e}. Falling back to intelligent heuristic tailoring.")

        return self._generate_heuristic_tailoring(job, profile)

    def _build_prompt(self, job: Dict[str, Any], profile: Dict[str, Any]) -> str:
        title = job.get("title", "Software Engineer")
        company = job.get("company", "Company")
        skills = ", ".join(job.get("skills", []))
        full_jd = job.get("full_jd_raw") or job.get("description") or "N/A"
        requirements = job.get("requirements") or "Xem full JD."

        master_cv_text = profile.get("master_cv_text", "").strip()
        ats_rules = profile.get("ats_rules", "").strip() or "Standard ATS scoring: prioritize core skills and quantify experience."
        cv_rules = profile.get("cv_rules", "").strip() or "Follow Google XYZ / STAR format, truthful experience selection, action verbs."

        candidate_context = ""
        if master_cv_text:
            candidate_context = f"""
### 2. CANDIDATE MASTER PORTFOLIO / RAW CV TEXT (EXTRACTED FROM UPLOADED PDF):
```text
{master_cv_text[:8000]}
```
"""
        else:
            profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
            candidate_context = f"""
### 2. CANDIDATE BASE PROFILE:
```json
{profile_json}
```
"""

        return f"""
You are an elite Executive Tech Recruiter and ATS Resume Optimization Specialist.
Your goal is to analyze the target Job Description (JD) and tailor the candidate's CV to maximize ATS keyword scoring, pass initial screening filters, and highlight relevant technical competencies truthfully.

---
### 1. TARGET JOB DESCRIPTION:
- Title: {title}
- Company: {company}
- Required Tech Stack: {skills}
- Key Requirements:
{requirements}

- Full JD Raw Content:
{full_jd[:4000]}

---
{candidate_context}

---
### 3. USER CUSTOM ATS EVALUATION RULES:
Strictly adhere to the following rules when evaluating fit and identifying skill gaps:
{ats_rules}

---
### 4. USER CUSTOM CV WRITING & TAILORING RULES:
Strictly adhere to the following rules when generating summary and experience bullets:
{cv_rules}

---
### 5. OUTPUT INSTRUCTIONS:
Produce a JSON object strictly matching this schema:
- match_score: integer from 0 to 100 based on realistic technical alignment against the JD.
- match_analysis: 2-3 sentences explaining candidate's top strengths and primary technical gaps.
- missing_skills: list of up to 5 critical technologies/methodologies mentioned in the JD that the candidate should be aware of.
- tailored_summary: A 3-4 sentence powerful professional summary tailored specifically for {title} at {company}, emphasizing the candidate's existing strengths while seamlessly integrating relevant JD keywords.
- tailored_bullets: 3-4 high-impact bullet points for the candidate's most recent position. Follow Google XYZ formula: "Accomplished [X] as measured by [Y] by doing [Z]", naturally featuring technical keywords from this JD.
"""

    def _call_gemini_api(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """Calls Google Gemini model with structured JSON output."""
        prompt = self._build_prompt(job, profile)

        if self._client:
            from google.genai import types
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
        else:
            # Fallback direct REST
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

        parsed = json.loads(raw_text)
        return GeminiTailorResponse(**parsed)

    def _call_openai_api(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """Calls OpenAI Chat Completions API with JSON object response."""
        prompt = self._build_prompt(job, profile)
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an elite Tech Recruiter and ATS Resume Specialist. Output valid JSON strictly matching the requested schema without any markdown formatting."},
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

    def _call_claude_api(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """Calls Anthropic Claude API."""
        prompt = self._build_prompt(job, profile)
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
        clean_json = self._extract_json_block(raw_text)
        parsed = json.loads(clean_json)
        return GeminiTailorResponse(**parsed)

    def _call_custom_api(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """Calls Custom OpenAI-compatible API (DeepSeek, Ollama, OpenRouter)."""
        prompt = self._build_prompt(job, profile)
        root_url = (self.base_url or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{root_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name or "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are an elite Tech Recruiter and ATS Resume Specialist. Output valid JSON strictly."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        with httpx.Client(timeout=40.0) as client:
            res = client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        clean_json = self._extract_json_block(content)
        parsed = json.loads(clean_json)
        return GeminiTailorResponse(**parsed)

    def _extract_json_block(self, text: str) -> str:
        """Extracts JSON block from text if wrapped in markdown code blocks."""
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        match_brace = re.search(r"(\{.*\})", text, re.DOTALL)
        if match_brace:
            return match_brace.group(1)
        return text

    def _generate_heuristic_tailoring(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """
        Intelligent offline fallback mode when no API Key is yet configured or network is unreachable.
        Analyzes overlaps between candidate profile and JD skills.
        """
        jd_skills = set(s.lower() for s in job.get("skills", []))
        user_skills = set()

        skills_dict = profile.get("skills", {})
        if isinstance(skills_dict, dict):
            for sublist in skills_dict.values():
                if isinstance(sublist, list):
                    for s in sublist:
                        user_skills.add(s.lower())

        master_cv_text = profile.get("master_cv_text", "").lower()
        matched = []
        missing = []

        for skill in jd_skills:
            if skill in user_skills or (master_cv_text and skill in master_cv_text):
                matched.append(skill.title())
            else:
                missing.append(skill.title())

        total = len(jd_skills)
        score = int((len(matched) / total * 35) + 60) if total > 0 else 75
        score = min(score, 95)

        title = job.get("title", "Kỹ sư phần mềm")
        company = job.get("company", "Công ty")

        summary = (
            f"Kỹ sư giàu nhiệt huyết với nền tảng vững chắc và thế mạnh kỹ thuật phù hợp cho vị trí {title} tại {company}. "
            f"Thành thạo trong các công nghệ cốt lõi {', '.join(matched[:3]) if matched else 'phát triển hệ thống'}, "
            f"luôn chủ động cập nhật các kỹ năng hiện đại và tối ưu hóa giải pháp theo chuẩn mực chất lượng cao."
        )

        bullets = [
            f"Thiết kế và tối ưu kiến trúc phần mềm sử dụng {matched[0] if matched else 'Python/FastAPI'}, cải thiện 30% hiệu năng và thông lượng xử lý hệ thống.",
            f"Hợp tác liên chức năng để chuẩn hóa quy trình triển khai và tích hợp liên tục (CI/CD), rút ngắn 40% chu kỳ phát hành sản phẩm.",
            f"Nghiên cứu áp dụng các công nghệ mục tiêu ({', '.join(missing[:2]) if missing else 'Containerization & Cloud'}), nâng cao tính mở rộng và khả năng giám sát vận hành.",
        ]

        analysis = (
            f"Hồ sơ đáp ứng tốt {len(matched)}/{total} kỹ năng trọng tâm của JD ({', '.join(matched[:3]) if matched else 'các kỹ năng cơ bản'}). "
            f"Cần lưu ý bổ sung hoặc nhấn mạnh kinh nghiệm với: {', '.join(missing[:3]) if missing else 'các công cụ quản lý dự án'} để đạt điểm tuyệt đối."
        )

        return GeminiTailorResponse(
            match_score=score,
            match_analysis=analysis,
            missing_skills=missing[:5],
            tailored_summary=summary,
            tailored_bullets=bullets,
        )


# Backward-compatible alias
GeminiService = MultiProviderAIService
