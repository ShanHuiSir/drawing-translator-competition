#!/bin/zsh
cd "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python run_app.py
fi
echo '请先运行 scripts/install_macos.sh 安装依赖。'
read -k 1
