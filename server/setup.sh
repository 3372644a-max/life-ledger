#!/bin/bash
# 人生账本 · 行情引擎一键部署脚本（在云服务器上以 root 运行）
# 用法：把整个 server 目录上传到服务器任意位置（如 /root/server），然后：
#   bash setup.sh
set -e

DIR=/opt/ledger-engine
SRC="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DIR/data"
cp "$SRC/ledger-engine.py" "$DIR/"

if [ ! -f "$DIR/token.txt" ] || [ ! -s "$DIR/token.txt" ]; then
  head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$DIR/token.txt"
  echo "[setup] 已生成访问令牌 token.txt"
fi

cat > /etc/systemd/system/ledger-engine.service <<EOF
[Unit]
Description=Life Ledger Market Engine
After=network.target

[Service]
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 $DIR/ledger-engine.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ledger-engine
sleep 1
systemctl --no-pager status ledger-engine | head -8

echo ""
echo "======================================"
echo "部署完成！你的行情令牌（填进 App 设置页）："
cat "$DIR/token.txt"
echo ""
echo "本地自检："
curl -s http://127.0.0.1:8787/health || echo "(health 检查失败，请查看 systemctl status ledger-engine)"
echo "======================================"
