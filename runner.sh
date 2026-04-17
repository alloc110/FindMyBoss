#!/bin/bash
# 1. Đi tới thư mục chứa code
cd /home/loc/job-scraper

# 2. Kích hoạt môi trường ảo
source venv/bin/activate


python3 main.py

# 5. Sau khi chạy xong, giải phóng tài nguyên
deactivate
echo "Cào xong lúc $(date)" >> crawl_log.txt
