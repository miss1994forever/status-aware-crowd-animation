#!/bin/zsh
set -eu
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$project_dir"
python3 scripts/build_progress_page.py
printf '\n请在浏览器打开：http://127.0.0.1:8769/progress/index.html\n保持这个终端窗口运行；按 Control+C 停止。\n\n'
python3 -m http.server 8769 --bind 127.0.0.1
