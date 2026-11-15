import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from services.applications_tracker import generate_applications_markdown, get_applications_markdown_path
from services.notifier import DiscordNotifier
from services.career_ops_service import CareerOpsService


async def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU KIỂM THỬ TRỰC TIẾP (LIVE TEST): CAREER-OPS & DISCORD")
    print("=" * 60)

    # 1. Test Applications.md generation
    print("\n[Bước 1] Sinh tệp data/applications.md...")
    md_content = generate_applications_markdown()
    md_path = get_applications_markdown_path()
    assert md_path.exists(), "Tệp applications.md không tồn tại!"
    print(f"✅ Đã tạo thành công tệp: {md_path}")
    print(f"   Dung lượng: {len(md_content)} ký tự")

    # 2. Test Sending applications.md to Discord
    print("\n[Bước 2] Gửi tệp applications.md sang Discord Webhook...")
    notifier = DiscordNotifier()
    if notifier._disabled:
        print("⚠️ DISCORD_WEBHOOK_URL chưa được cấu hình trong .env!")
    else:
        sent_tracker = await notifier.send_applications_tracker()
        if sent_tracker:
            print("✅ Đã bắn tệp applications.md thành công vào Discord!")
        else:
            print("❌ Gửi applications.md thất bại (kiểm tra lại webhook URL).")

    # 3. Test Full Intake: URL -> Scrape -> ATS Tailor -> PDF -> Discord Webhook
    print("\n[Bước 3] Thử nghiệm Fast Intake với 1 link tuyển dụng thực tế...")
    service = CareerOpsService()
    test_url = "https://itviec.com/viec-lam-it/senior-python-backend-engineer"

    result = await service.process_job_url(
        url=test_url,
        template="classic",
        send_to_discord=True,
    )

    print(f"✅ Kết quả xử lý công việc:")
    print(f"   - Job ID: #{result['job_id']}")
    print(f"   - Tiêu đề: {result['job']['title']}")
    print(f"   - Công ty: {result['job']['company']}")
    print(f"   - Điểm ATS Match: {result['match_score']}%")
    print(f"   - File CV PDF: {result['pdf_path']}")
    print(f"   - Trạng thái gửi Discord (Embed + PDF): {'Thành công ✅' if result['discord_sent'] else 'Thất bại ❌'}")

    print("\n" + "=" * 60)
    print("🎉 KIỂM THỬ HOÀN TẤT THÀNH CÔNG!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
