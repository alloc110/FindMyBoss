"""
Curated model catalog across all supported AI providers.
"""
from typing import Any, Dict

MODEL_CATALOG: Dict[str, Any] = {
    "gemini": {
        "name": "Google Gemini",
        "key_label": "Google Gemini API Key",
        "placeholder": "Dán mã API Key của bạn (bắt đầu bằng AIzaSy...)",
        "hint": "Lấy API Key miễn phí tại Google AI Studio (aistudio.google.com). Nếu để trống, hệ thống sẽ chạy ở Chế độ Mô phỏng Thông minh.",
        "models": [
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (High)", "desc": "Mô hình Gemini 3.8 Flash thế hệ mới - Siêu tốc độ, suy luận logic vượt trội", "tag": "Mới nhất 3.8"},
            {"id": "gemini-3.0-pro", "name": "Gemini 3.0 Pro", "desc": "Mô hình Gemini 3.0 Pro Flagship - Tư duy chiều sâu, giải quyết vấn đề phức tạp", "tag": "Flagship 3.0"},
            {"id": "gemini-3.0-flash", "name": "Gemini 3.0 Flash", "desc": "Mô hình Gemini 3.0 Flash - Cân bằng hoàn hảo tốc độ và độ chính xác", "tag": "Mới nhất 3.0"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "desc": "Khuyên dùng - Cực nhanh, thông minh & chuẩn xác nhất", "tag": "Khuyên dùng"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "desc": "Lập luận sâu, phân tích JD học thuật & tối ưu CV toàn diện", "tag": "Lý luận sâu"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "desc": "Tốc độ cao thế hệ mới, đa phương thức tối ưu", "tag": "Tốc độ cao"},
            {"id": "gemini-2.0-flash-thinking-exp-01-21", "name": "Gemini 2.0 Flash Thinking", "desc": "Suy luận logic từng bước, tối ưu từ khóa ATS chuyên sâu", "tag": "Tư duy AI"},
            {"id": "gemini-2.0-pro-exp-02-05", "name": "Gemini 2.0 Pro Experimental", "desc": "Mô hình lập trình & coding mạnh mẽ nhất của Google", "tag": "Chuyên gia Tech"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "desc": "Cửa sổ ngữ cảnh 2M token siêu lớn cho JD dài", "tag": "Ngữ cảnh lớn"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "desc": "Tiết kiệm token & phản hồi nhanh", "tag": "Tiết kiệm"},
            {"id": "custom", "name": "Mô hình Gemini tùy chỉnh...", "desc": "Tự nhập ID mô hình (VD: gemini-3.0-ultra, preview...)", "tag": "Tùy biến"},
        ],
    },
    "openai": {
        "name": "OpenAI / ChatGPT",
        "key_label": "OpenAI API Key",
        "placeholder": "Dán mã OpenAI API Key của bạn (bắt đầu bằng sk-...)",
        "hint": "Lấy API Key tại platform.openai.com/api-keys. Hỗ trợ các dòng GPT-4o, GPT-3.5-Turbo và dòng suy luận o1/o3.",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "desc": "Mô hình đa năng hàng đầu của OpenAI", "tag": "Flagship"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "desc": "Chi phí rẻ, tốc độ siêu tốc, tối ưu hóa CV chuẩn", "tag": "Tiết kiệm"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "desc": "Mô hình ChatGPT kinh điển, độ ổn định cao", "tag": "Kinh điển"},
            {"id": "o1-mini", "name": "OpenAI o1 Mini", "desc": "Mô hình tư duy chuyên sâu Reasoning", "tag": "Suy luận"},
            {"id": "o3-mini", "name": "OpenAI o3 Mini", "desc": "Mô hình Reasoning thế hệ mới", "tag": "Lý luận cao"},
            {"id": "custom", "name": "Mô hình OpenAI tùy chỉnh...", "desc": "Tự nhập ID mô hình", "tag": "Tùy biến"},
        ],
    },
    "claude": {
        "name": "Anthropic Claude",
        "key_label": "Anthropic Claude API Key",
        "placeholder": "Dán mã Anthropic API Key của bạn (bắt đầu bằng sk-ant-...)",
        "hint": "Lấy API Key tại console.anthropic.com. Claude nổi tiếng về chất lượng viết văn tự nhiên, học thuật và chính xác.",
        "models": [
            {"id": "claude-3-7-sonnet-latest", "name": "Claude 3.7 Sonnet", "desc": "Mô hình mới nhất với khả năng viết lách & tư duy xuất sắc", "tag": "Mới nhất"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "desc": "Chuẩn mực phân tích ATS và viết văn phong chuyên nghiệp", "tag": "Khuyên dùng"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "desc": "Tốc độ xử lý tức thì, chi phí tối ưu", "tag": "Tốc độ"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "desc": "Mô hình năng lực tối đa cho tác vụ phức tạp", "tag": "Chuyên sâu"},
            {"id": "custom", "name": "Mô hình Claude tùy chỉnh...", "desc": "Tự nhập ID mô hình", "tag": "Tùy biến"},
        ],
    },
    "custom": {
        "name": "Tùy biến / DeepSeek / Local LLM",
        "key_label": "Custom API Key (Tùy chọn)",
        "placeholder": "Dán mã API Key (sk-...) hoặc để trống nếu chạy Ollama local",
        "hint": "Tương thích với mọi API chuẩn OpenAI: DeepSeek (api.deepseek.com), Ollama (localhost:11434), vLLM, OpenRouter.",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3 (Chat)", "desc": "Mô hình mã nguồn mở chi phí siêu rẻ", "tag": "Hiệu năng cao"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (Reasoner)", "desc": "Mô hình tư duy lập luận sâu", "tag": "Suy luận"},
            {"id": "custom", "name": "Mô hình tùy chỉnh khác...", "desc": "Tự nhập model cho Ollama / OpenRouter", "tag": "Tùy biến"},
        ],
    },
}
