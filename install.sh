#!/usr/bin/env bash
#
# 玄源 · dsh 修真内核 —— 一键植入脚本
#
# 作用：把玄源插件 + 技能包装进你的 dsh，让"境界/心境/道韵"每轮注入 agent 循环。
#   - 核心（零依赖，默认）：cordis 插件 + 全部技能（总纲/境界/心境道韵/HYBRID 元方法论），任何人复制即生效。
#   - 引擎（可选，--mcp）：xuanyuan-mcp 状态机引擎，需要 Python + pip install mcp。
#
# 用法：
#   ./install.sh            # 装核心（插件 + 技能）
#   ./install.sh --mcp      # 额外装 MCP 引擎
#   DSH_PROFILE=~/.dsh/profiles/web ./install.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WITH_MCP=0
for a in "$@"; do [ "$a" = "--mcp" ] && WITH_MCP=1; done

# 1) 定位 dsh
DSH_PROFILE="${DSH_PROFILE:-$HOME/.dsh/profiles/web}"
if [ ! -f "$DSH_PROFILE/cordis.patch.yml" ]; then
  echo "✗ 找不到 dsh 配置：$DSH_PROFILE/cordis.patch.yml"
  echo "  请设置 DSH_PROFILE 指向你的 dsh profile 目录（含 cordis.patch.yml）。"
  exit 1
fi
PROFILES_DIR="$(cd "$DSH_PROFILE/.." && pwd)"
NODE_MODULES="$PROFILES_DIR/node_modules"
PATCH="$DSH_PROFILE/cordis.patch.yml"
echo "✓ dsh profile: $DSH_PROFILE"

# 2) 装 cordis 插件包（@xuanyuan/dsh-xuanyuan）到 node_modules
PLUGIN_DEST="$NODE_MODULES/@xuanyuan/dsh-xuanyuan"
echo "→ 安装插件到 $PLUGIN_DEST"
mkdir -p "$PLUGIN_DEST"
cp -R "$REPO_ROOT/plugin/package.json" "$PLUGIN_DEST/"
cp -R "$REPO_ROOT/plugin/lib" "$PLUGIN_DEST/"
echo "✓ 插件已就位"

# 3) 幂等写入 cordis.patch.yml 的 insert 块（合并进已有 insert 列表，不打掉 mcp 等已有项）
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then PY="/opt/homebrew/bin/python3"; fi
"$PY" - "$PATCH" <<'PYEOF'
import sys
# cordis.patch.yml 是「列表结构」：每个顶层项是 `- insert:`。
# 因此 xuanyuan 必须以「新的列表项」形式追加，绝不能写顶层 `insert:`（会变成重复键、吞掉其它 insert）。
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
marker = "name: '@xuanyuan/dsh-xuanyuan'"
if any(marker in ln for ln in lines):
    print("✓ cordis 已包含 xuanyuan（跳过）")
    sys.exit(0)
block = [
    "\n",
    "- insert:\n",
    "  - id: xuanyuan\n",
    "    name: '@xuanyuan/dsh-xuanyuan'\n",
    "    config: {}\n",
]
if lines and not lines[-1].endswith("\n"):
    lines[-1] += "\n"
lines.extend(block)
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("✓ cordis.patch.yml 已追加 xuanyuan insert（列表项）")
PYEOF

# 4) 装技能包（零依赖，复制即生效）
AGENTS_SKILLS="$HOME/.agents/skills"
mkdir -p "$AGENTS_SKILLS"
for d in "$REPO_ROOT"/skills/*/; do
  name="$(basename "$d")"
  cp -R "$d" "$AGENTS_SKILLS/$name"
  echo "✓ 技能已装: $name"
done

# 5) 可选：MCP 引擎
if [ "$WITH_MCP" = "1" ]; then
  SERVER="$REPO_ROOT/mcp/xuanyuan-mcp/server.py"
  VENV="$HOME/.dsh/xuanyuan/venv"
  echo "→ 准备 MCP 引擎（venv + pip install mcp）"
  if [ ! -x "$VENV/bin/python" ]; then
    "$(command -v python3 || echo /opt/homebrew/bin/python3)" -m venv "$VENV"
  fi
  "$VENV/bin/python" -m pip install -q -r "$REPO_ROOT/mcp/xuanyuan-mcp/requirements.txt"
  PYBIN="$VENV/bin/python"

  # 写入 mcp-client insert 块（幂等）
  "$PY" - "$PATCH" "$SERVER" "$PYBIN" <<'PYEOF'
import sys
# 同样以「新的列表项」形式追加，避免顶层 insert: 重复键。
path, server, pybin = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
if any("id: xuanyuan-mcp" in ln for ln in lines):
    print("✓ cordis 已包含 xuanyuan-mcp（跳过）")
    sys.exit(0)
block = [
    "\n",
    "- insert:\n",
    "  - id: xuanyuan-mcp\n",
    "    name: '@deepseek-ai/dsh-mcp-client'\n",
    "    config:\n",
    "      serverName: xuanyuan\n",
    "      transport: stdio\n",
    "      command: " + pybin + "\n",
    "      args:\n",
    "        - " + server + "\n",
    "      env: {}\n",
    "      failOnStartupError: false\n",
]
if lines and not lines[-1].endswith("\n"):
    lines[-1] += "\n"
lines.extend(block)
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("✓ cordis 已追加 xuanyuan-mcp（mcp-client 桥，列表项）")
PYEOF
  echo "✓ MCP 引擎已接线"
fi

# 6) 重启 dsh（优先 launchd，否则提示手动重启）
PLIST="$HOME/Library/LaunchAgents/com.user.dsh-web.plist"
if launchctl list 2>/dev/null | grep -q "com.user.dsh-web"; then
  echo "→ 重启 dsh（launchd）"
  launchctl kickstart -k "gui/$(id -u)/com.user.dsh-web" 2>/dev/null || \
    launchctl kickstart -k com.user.dsh-web 2>/dev/null || true
  sleep 6
  if lsof -nP -iTCP:3081 -sTCP:LISTEN 2>/dev/null | grep -q LISTEN; then
    echo "✓ dsh 已重启并监听 3081"
  else
    echo "⚠ dsh 未自动起来，请手动重启 dsh"
  fi
else
  echo "→ 未检测到 launchd 托管的 dsh，请手动重启 dsh 使插件生效。"
fi

echo
echo "════════════════════════════════════════════"
echo " 玄源 · dsh 修真内核 植入完成"
echo " 核心：插件(@xuanyuan/dsh-xuanyuan) + 10 个 xuanyuan-* 技能（总纲/境界/心境道韵/HYBRID 元方法论）"
if [ "$WITH_MCP" = "1" ]; then
  echo " 引擎：xuanyuan-mcp 已接线（工具前缀 mcp__xuanyuan__*）"
else
  echo " 引擎：未装（如需主动状态机，重跑 ./install.sh --mcp）"
fi
echo " 去 dsh 里随便聊一句，观察顶部是否出现【玄源 · 修真内核 · 当前运行状态】"
echo "════════════════════════════════════════════"
