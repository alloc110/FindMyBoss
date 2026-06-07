#!/bin/bash

# 1. Navigate to the absolute project root directory
cd /home/loc/job-scraper || { echo "CRITICAL: Project directory not found!" && exit 1; }

# 2. Inject pipeline secrets into environment variables
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1493247072072106095/aUteZgerI29WJN0_UJtCmEu4Hh_RViv3DIahNj4rGF1J3kGHJmEhV6KWtKvpQu9lfweH"

# 3. Execute the orchestrator directly using the virtual environment's binary
# MẸO: Hãy chắc chắn file chạy tổng của bạn tên là run_scraper.py (file tụi mình vừa sửa) hay main.py nhé!
/home/loc/venv/bin/python3 main.py

# 4. Log completion metrics using absolute paths to prevent tracking loss
echo "Pipeline execution finished successfully at: $(date)" >> /home/loc/job-scraper/crawl_log.txt