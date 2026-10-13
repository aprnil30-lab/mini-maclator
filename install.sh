#!/usr/bin/env bash
set -e

echo "=================================================="
echo "    MiniMaclator 一键安装与环境配置脚本"
echo "=================================================="

# 1. 检测 Python3
if ! command -v python3 &> /dev/null; then
    echo "[-] 未检测到 Python3，正在安装..."
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y python3 python3-pip
    elif command -v brew &> /dev/null; then
        brew install python
    else
        echo "[-] 请先手动安装 Python 3.9+"
        exit 1
    fi
fi

# 2. 安装底层依赖 (Unicorn 模拟器引擎 + Capstone 反汇编器)
echo "[+] 正在安装底层依赖库 (unicorn, capstone)..."
pip3 install --break-system-packages unicorn capstone 2>/dev/null || pip3 install --user unicorn capstone || pip3 install unicorn capstone

# 3. 创建全局启动命令软链接
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_PATH="/usr/local/bin/maclator"

echo "[+] 正在配置全局命令: maclator ($BIN_PATH)..."
mkdir -p /usr/local/bin

cat <<EOF > "$BIN_PATH"
#!/usr/bin/env bash
if [ -z "\$1" ]; then
    echo "使用方式: maclator <ARM64_Mach-O文件路径>"
    exit 1
fi
PYTHONPATH="$INSTALL_DIR/src" python3 -c "import sys; from engine import MiniMaclator; m = MiniMaclator(); m.run_macho(sys.argv[1])" "\$@"
EOF

chmod +x "$BIN_PATH"

echo "=================================================="
echo "✅ 安装成功！"
echo "使用方法: maclator <你的ARM64_Mach-O文件路径>"
echo "运行测试: python3 $INSTALL_DIR/tests/test_full.py"
echo "=================================================="
