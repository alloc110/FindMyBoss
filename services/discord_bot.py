import asyncio
import os
import re
import sys
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import discord
    from discord.ext import commands
    HAS_DISCORD_PY = True
except ImportError:
    discord = None  # type: ignore
    commands = None  # type: ignore
    HAS_DISCORD_PY = False

from core.config import config, get_logger
from models.Job import Job
from services.career_ops_service import CareerOpsService

logger = get_logger("DiscordBot")

URL_REGEX = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&//=]*")


def create_discord_bot(
    token: Optional[str] = None,
    career_ops_service: Optional[CareerOpsService] = None,
    require_message_content: bool = True
):
    """Factory creating and configuring the Discord Bot client."""
    if not HAS_DISCORD_PY:
        logger.error("❌ discord.py is not installed. Install via pip install discord.py")
        return None

    bot_token = token or config.discord_bot_token
    if not bot_token:
        logger.warning("⚠️ DISCORD_BOT_TOKEN is not set. Discord Bot listener will not connect.")
        return None

    intents = discord.Intents.default()
    if require_message_content:
        intents.message_content = True
    intents.messages = True

    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    service = career_ops_service or CareerOpsService()

    @bot.event
    async def on_ready():
        logger.info(f"🤖 FindMyBoss Discord Bot logged in as: {bot.user} (ID: {bot.user.id})")
        if require_message_content:
            logger.info("📡 Đang lắng nghe: gõ !help, !career <url>, hoặc dán link tuyển dụng trực tiếp vào kênh.")
        else:
            logger.info("📡 Chế độ Fallback: Gọi bot bằng cách TAG @Bot (vd: @FindMyBoss !help hoặc @FindMyBoss <url>) hoặc gửi tin nhắn riêng (DM).")

    @bot.event
    async def on_message(message: discord.Message):
        # Ignore own messages or bot messages
        if message.author.bot or message.author == bot.user:
            return

        content = message.content.strip()

        # If bot is mentioned in message, strip the mention prefix
        if bot.user in message.mentions:
            content = re.sub(rf"<@!?{bot.user.id}>", "", content).strip()

        # 1. Command: !help or help
        if content.lower() in ["!help", "!commands", "help"]:
            help_embed = discord.Embed(
                title="🤖 FindMyBoss & Career-Ops Discord Bot — Hướng Dẫn",
                description="Hệ thống tự động cào tin tuyển dụng, đối soát ATS và tạo CV cá nhân hóa.",
                color=0x10B981,
            )
            help_embed.add_field(
                name="⚡ Phân tích & Tạo CV tức thì:",
                value="`!career <link_tuyển_dụng>` hoặc dán trực tiếp link bài đăng vào kênh.\nBot sẽ tự cào JD, tính điểm ATS và gửi lại CV PDF đính kèm.",
                inline=False,
            )
            help_embed.add_field(
                name="📋 Bảng theo dõi Applications.md:",
                value="`!applications` hoặc `!tracker` — Xuất và đính kèm tệp `applications.md` tổng kết toàn bộ việc làm & điểm ATS.",
                inline=False,
            )
            help_embed.add_field(
                name="🎯 Xem chi tiết điểm ATS:",
                value="`!ats <job_id>` — Xem bảng phân tích chi tiết kỹ năng đạt & thiếu của Job ID.",
                inline=False,
            )
            help_embed.add_field(
                name="📄 Tải CV của Job:",
                value="`!cv <job_id>` — Tải lại file PDF CV đã được tạo cho Job ID.",
                inline=False,
            )
            help_embed.set_footer(text="FindMyBoss")
            await message.reply(embed=help_embed)
            return

        # 2. Command: !applications or !tracker
        if content.lower() in ["!applications", "!tracker", "!apps"]:
            try:
                from services.applications_tracker import generate_applications_markdown, get_applications_markdown_path

                generate_applications_markdown(service.storage)
                tracker_path = get_applications_markdown_path()

                jobs, total = service.storage.get_jobs(limit=5)
                tailored_count = sum(1 for j in jobs if j.get("cv_id"))

                embed = discord.Embed(
                    title="📋 Danh Sách Tuyển Dụng & Đơn Ứng Tuyển (Applications Tracker)",
                    description=(
                        f"📊 **Tổng số việc:** `{total}` | **Đã tạo CV:** `{tailored_count}`\n"
                        f"Toàn bộ bảng theo dõi đã được cập nhật vào tệp `applications.md` đính kèm bên dưới:"
                    ),
                    color=0x3498DB,
                )

                for j in jobs[:5]:
                    score_str = f"🎯 {j.get('match_score')}%" if j.get("match_score") else "Chưa chấm"
                    embed.add_field(
                        name=f"#{j['id']} - {j['company']} ({score_str})",
                        value=f"**{j['title']}**\n[Xem JD]({j['link']}) • Trạng thái: `{j.get('status', 'saved')}`",
                        inline=False,
                    )

                embed.set_footer(text="Mở file applications.md đính kèm để xem đầy đủ chi tiết.")

                file = discord.File(str(tracker_path), filename="applications.md")
                await message.reply(embed=embed, file=file)
            except Exception as e:
                logger.error(f"Error serving applications.md in Discord Bot: {e}")
                await message.reply(f"❌ Không thể tạo file applications.md: `{e}`")
            return

        # 3. Command: !ats <job_id>
        ats_match = re.match(r"^!ats\s+(\d+)", content, re.IGNORECASE)
        if ats_match:
            job_id = int(ats_match.group(1))
            job = service.storage.get_job_by_id(job_id)
            if not job:
                await message.reply(f"❌ Không tìm thấy Job #{job_id} trong hệ thống.")
                return

            score = job.get("match_score") or 0
            if score >= 80:
                score_badge = "🟢 Tốt"
                color = 0x2ECC71
            elif score >= 60:
                score_badge = "🟡 Có thể"
                color = 0xF1C40F
            else:
                score_badge = "🔴 Không hợp"
                color = 0xE74C3C

            ats_embed = discord.Embed(
                title=f"🎯 Báo Cáo Phân Tích ATS — Job #{job_id}",
                url=job.get("link"),
                description=f"**{job['title']}** tại **{job['company']}**\n\n🎯 **Match Score:** **{score}%** ({score_badge})",
                color=color,
            )

            if job.get("skills"):
                ats_embed.add_field(
                    name="🛠️ Tech Stack Yêu Cầu",
                    value=" ".join([f"`{s}`" for s in job["skills"][:10]]),
                    inline=False,
                )

            missing = job.get("missing_skills") or []
            if missing:
                ats_embed.add_field(
                    name="⚠️ Từ Khóa ATS Cần Bổ Sung Trong CV",
                    value=" ".join([f"`{s}`" for s in missing[:8]]),
                    inline=False,
                )

            summary = job.get("tailored_summary")
            if summary:
                ats_embed.add_field(
                    name="💡 Tóm Tắt Kinh Nghiệm Tối Ưu",
                    value=summary[:1000],
                    inline=False,
                )

            bullets = job.get("tailored_bullets") or []
            if bullets:
                bullets_formatted = "\n".join([f"• {b}" for b in bullets[:3]])
                ats_embed.add_field(
                    name="✨ Bullet Points Gợi Ý Theo Công Thức STAR",
                    value=bullets_formatted[:1000],
                    inline=False,
                )

            ats_embed.set_footer(text=f"FindMyBoss 🎯 • Gõ !cv {job_id} để tải file CV PDF")
            await message.reply(embed=ats_embed)
            return

        # 4. Command: !cv <job_id>
        cv_match = re.match(r"^!cv\s+(\d+)", content, re.IGNORECASE)
        if cv_match:
            job_id = int(cv_match.group(1))
            job = service.storage.get_job_by_id(job_id)
            if not job:
                await message.reply(f"❌ Không tìm thấy Job #{job_id}.")
                return

            pdf_path = job.get("pdf_path")
            if pdf_path and os.path.isfile(pdf_path):
                safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", job['title'][:25])
                file = discord.File(pdf_path, filename=f"CV_{job['company']}_{safe_title}.pdf")
                await message.reply(content=f"📄 **CV PDF cho Job #{job_id}:** {job['title']} ({job['company']})", file=file)
            else:
                await message.reply(f"⚠️ Job #{job_id} chưa có file CV PDF. Hãy dùng lệnh: `!career {job['link']}` để tạo lại.")
            return

        # 5. Check for command prefix or direct URLs
        target_url = None
        command_match = re.match(r"^!(?:career|apply|tailor|job)\s+(https?://\S+)", content, re.IGNORECASE)
        if command_match:
            target_url = command_match.group(1).strip()
        else:
            # Check if message contains a valid URL
            found_urls = URL_REGEX.findall(content)
            if found_urls:
                target_url = found_urls[0].strip()

        if not target_url:
            await bot.process_commands(message)
            return

        logger.info(f"📥 Received job URL from {message.author} in #{message.channel}: {target_url}")

        try:
            # Visual feedback: React with hourglass
            await message.add_reaction("⏳")
        except Exception:
            pass

        status_msg = await message.reply(
            f"🔍 **Đang xử lý qua Career-Ops:**\n"
            f"• Cào dữ liệu JD từ: `{target_url[:80]}...`\n"
            f"• Đối soát CV & tính điểm ATS Match...\n"
            f"• Đang biên dịch PDF ATS chất lượng cao..."
        )

        try:
            # Process URL through career-ops service
            result = await service.process_job_url(
                url=target_url,
                send_to_discord=False,  # Bot will reply directly in this channel
            )

            job = result["job"]
            match_score = result.get("match_score", 75)
            tailored_summary = result.get("tailored_summary", "")
            missing_skills = result.get("missing_skills", [])
            pdf_path = result.get("pdf_path")

            # Craft clean Discord Embed matching Bot Viên layout
            job_obj = Job(
                title=job.get("title", ""),
                company=job.get("company", ""),
                link=job.get("link", ""),
                salary=job.get("salary", "Thoả thuận"),
                address=job.get("address", "Việt Nam"),
                exp=job.get("exp"),
                posted_date=job.get("posted_date", "Hôm nay"),
                image=job.get("image"),
                skills=job.get("skills", []),
                match_score=match_score,
            )
            embed_dict = job_obj.to_discord_embed()
            embed = discord.Embed.from_dict(embed_dict)

            # Attach generated CV PDF
            discord_file = None
            if pdf_path and os.path.isfile(pdf_path):
                safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", job['title'][:25])
                clean_filename = f"CV_{safe_title}.pdf"
                discord_file = discord.File(pdf_path, filename=clean_filename)

            # Reply with result and clean format
            if discord_file:
                await status_msg.edit(
                    content=None,
                    embed=embed,
                    attachments=[discord_file],
                )
            else:
                await status_msg.edit(
                    content=None,
                    embed=embed,
                )

            try:
                await status_msg.add_reaction("✅")
                await status_msg.add_reaction("❌")
            except Exception:
                pass

            try:
                await message.remove_reaction("⏳", bot.user)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ Error processing job URL in Discord Bot: {e}", exc_info=True)
            try:
                await message.remove_reaction("⏳", bot.user)
                await message.add_reaction("❌")
            except Exception:
                pass

            await status_msg.edit(
                content=f"❌ **Lỗi khi xử lý link tuyển dụng:** `{str(e)}`\n"
                        f"Vui lòng kiểm tra lại URL hoặc thử lại sau ít phút."
            )

    return bot


async def run_bot_async(token: Optional[str] = None):
    """Runs the discord bot asynchronously."""
    bot_token = token or config.discord_bot_token or os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token:
        logger.warning("DISCORD_BOT_TOKEN is not set. Bot runner aborted.")
        return

    bot = create_discord_bot(token=bot_token)
    if not bot:
        return

    try:
        await bot.start(bot_token)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n" + "=" * 65)
        print("⚠️ CHƯA BẬT PRIVILEGED INTENT (MESSAGE CONTENT INTENT)")
        print("Bot sẽ chuyển sang chế độ FALLBACK (vẫn hoạt động tốt!):")
        print(" 👉 Bạn có thể gọi bot bằng cách TAG @Bot: vd '@TênBot !help' hoặc '@TênBot <link>'")
        print(" 👉 Hoặc nhắn tin trực tiếp (DM) cho Bot.")
        print("")
        print("👉 ĐỂ GÕ TRỰC TIẾP '!help' KHÔNG CẦN TAG @Bot (mất 15 giây):")
        print(" 1. Mở: https://discord.com/developers/applications")
        print(" 2. Chọn Bot -> Chọn tab 'Bot' ở thanh bên trái")
        print(" 3. Cuộn xuống phần 'Privileged Gateway Intents'")
        print(" 4. BẬT XANH: 'MESSAGE CONTENT INTENT'")
        print(" 5. Bấm 'Save Changes' ở dưới cùng")
        print("=" * 65 + "\n")
        logger.warning("Starting bot in Fallback mode (mention-based)...")
        if not bot.is_closed():
            await bot.close()

        fallback_bot = create_discord_bot(token=bot_token, require_message_content=False)
        if fallback_bot:
            try:
                await fallback_bot.start(bot_token)
            except Exception as fe:
                logger.error(f"Fallback Discord Bot error: {fe}")
            finally:
                if not fallback_bot.is_closed():
                    await fallback_bot.close()
    except discord.errors.LoginFailure:
        print("❌ Lỗi Token: Token Discord Bot không hợp lệ. Vui lòng kiểm tra lại DISCORD_BOT_TOKEN trong file .env.")
        logger.error("Discord Bot LoginFailure: invalid bot token.")
    except Exception as e:
        logger.error(f"Discord Bot stopped with error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ Vui lòng thiết lập biến môi trường DISCORD_BOT_TOKEN trong file .env")
        exit(1)

    print("🚀 Khởi động FindMyBoss Career-Ops Discord Bot...")
    asyncio.run(run_bot_async(token))
