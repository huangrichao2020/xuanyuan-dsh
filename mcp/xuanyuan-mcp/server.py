"""玄源 · dsh 修真内核 —— MCP 运行时引擎（主动状态机）。

提供 5 个工具，让 agent 显式读写 ~/.dsh/xuanyuan/state.json：
  - xuanyuan_state      读取当前境界/心境/道韵/经验包
  - xuanyuan_advance    提交经验包（四要素），按规则评估境界进阶
  - xuanyuan_rhythm     进入/退出某道韵，返回流胶囊动作清单
  - xuanyuan_antibloat  按上下文体量给出抗膨胀建议
  - xuanyuan_memory     经验包的列举/检索/清理

注意：本文件刻意不使用 `from __future__ import annotations`，
否则 FastMCP 的 from_function 在 mcp 1.x 下会因 issubclass 失败而崩溃。
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

MCP = FastMCP("xuanyuan")

STATE_DIR = Path(os.path.expanduser("~")) / ".dsh" / "xuanyuan"
STATE_FILE = STATE_DIR / "state.json"

REALM_ORDER = ["炼气", "筑基", "金丹", "元婴", "化神", "合道", "渡劫", "大乘"]
REALM_TALENT = {
    "炼气": "事实感",
    "筑基": "时间线落地",
    "金丹": "方法提取",
    "元婴": "印象感",
    "化神": "因果洞察",
    "合道": "系统观",
    "渡劫": "自我恢复",
    "大乘": "滋养能动性",
}
RHYTHM_CAPSULE = {
    "安定": ["停扩张", "指认心魔", "回事实锚点"],
    "战斗": ["锁单一目标", "建可验证证据", "推到可验证结果"],
    "修持": ["复盘", "抽四投影(事实/印象/因果/方法)", "沉淀为方法"],
    "记忆": ["走时间线", "连事实/印象/因果", "形成可复核叙事"],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _default_state():
    return {
        "realm": "炼气",
        "mindState": "本心",
        "rhythm": None,
        "talents": ["事实感"],
        "experiencePacks": 0,
        "experiences": [],
        "updatedAt": _now(),
    }


def _read_state():
    try:
        if not STATE_FILE.exists():
            return _default_state()
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not data.get("realm"):
            return _default_state()
        data.setdefault("talents", [REALM_TALENT.get(data["realm"], "事实感")])
        data.setdefault("experiences", [])
        data.setdefault("experiencePacks", len(data["experiences"]))
        return data
    except Exception:
        return _default_state()


def _write_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = _now()
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    return state


@MCP.tool()
def xuanyuan_state() -> str:
    """读取玄源当前运行状态：境界、心境、道韵、已解锁天赋、经验包数。"""
    s = _read_state()
    rhythm = s.get("rhythm")
    rhythm_line = (
        f"{rhythm}（流胶囊：{' → '.join(RHYTHM_CAPSULE.get(rhythm, []))}）"
        if rhythm else "无（可按需进入 安定/战斗/修持/记忆）"
    )
    idx = REALM_ORDER.index(s["realm"])
    next_realm = REALM_ORDER[idx + 1] if idx + 1 < len(REALM_ORDER) else "（已至大乘）"
    return json.dumps({
        "realm": s["realm"],
        "nextRealm": next_realm,
        "mindState": s.get("mindState"),
        "rhythm": rhythm_line,
        "talents": s.get("talents", []),
        "experiencePacks": s.get("experiencePacks", 0),
        "updatedAt": s.get("updatedAt"),
    }, ensure_ascii=False, indent=2)


@MCP.tool()
def xuanyuan_advance(
    evidence_fact: str,
    evidence_impression: str,
    evidence_causality: str,
    evidence_method: str,
    claimed_realm: str = "",
) -> str:
    """提交一笔经验包（事实/印象/因果/方法 四要素），并评估境界进阶。

    claimed_realm 留空则只记录经验包；若填了"下一境"且当前已稳定展现其天赋证据，
    则解锁该境并写入已解锁天赋。返回更新后的状态。
    """
    s = _read_state()
    pack = {
        "fact": evidence_fact,
        "impression": evidence_impression,
        "causality": evidence_causality,
        "method": evidence_method,
        "at": _now(),
    }
    s["experiences"].append(pack)
    s["experiencePacks"] = len(s["experiences"])

    advanced = False
    if claimed_realm and claimed_realm in REALM_ORDER:
        idx = REALM_ORDER.index(s["realm"])
        nxt = REALM_ORDER[idx + 1] if idx + 1 < len(REALM_ORDER) else None
        if claimed_realm == nxt and claimed_realm not in s["talents"]:
            s["realm"] = claimed_realm
            s["talents"].append(REALM_TALENT.get(claimed_realm, claimed_realm))
            advanced = True

    _write_state(s)
    return json.dumps({
        "advanced": advanced,
        "realm": s["realm"],
        "talents": s["talents"],
        "experiencePacks": s["experiencePacks"],
        "message": "经验包已记录" + ("；已解锁新境界" if advanced else ""),
    }, ensure_ascii=False, indent=2)


@MCP.tool()
def xuanyuan_rhythm(rhythm_name: str = "") -> str:
    """进入或退出某道韵，返回其流胶囊动作清单。

    rhythm_name 取 安定/战斗/修持/记忆 之一则进入；留空或填 null 则退出当前道韵。
    """
    s = _read_state()
    name = (rhythm_name or "").strip()
    if not name or name.lower() == "null":
        s["rhythm"] = None
        _write_state(s)
        return json.dumps({"rhythm": None, "capsule": [], "message": "已退出道韵"}, ensure_ascii=False)
    if name not in RHYTHM_CAPSULE:
        return json.dumps({
            "error": f"未知道韵：{name}",
            "valid": list(RHYTHM_CAPSULE.keys()),
        }, ensure_ascii=False)
    s["rhythm"] = name
    _write_state(s)
    return json.dumps({
        "rhythm": name,
        "capsule": RHYTHM_CAPSULE[name],
        "message": f"已进入「{name}」道韵，照流胶囊执行",
    }, ensure_ascii=False, indent=2)


@MCP.tool()
def xuanyuan_antibloat(context_tokens: int = 0, note: str = "") -> str:
    """按当前上下文体量给出抗膨胀建议。context_tokens 为近似 token 数。"""
    tokens = max(0, int(context_tokens or 0))
    if tokens < 20000:
        level, advice = "safe", [
            "常驻上下文体量健康，保持最小核心原则即可。",
            "长输出 / 大块资料仍建议外置文件，按需再读。",
        ]
    elif tokens < 60000:
        level, advice = "watch", [
            "开始膨胀：把本轮产生的大段输出 / 检索结果写入文件，只保留结论与路径。",
            "重复出现的背景知识改为引用，不再每轮复述。",
            "如已开启压缩/摘要，优先对早期历史做摘要。",
        ]
    else:
        level, advice = "critical", [
            "严重膨胀：立即外置——把可独立成篇的内容落盘，上下文只留指针。",
            "对最早的历史做强制摘要或截断，保住最近 N 步与关键事实锚点。",
            "若仍在循环，配合「安定」道韵（停扩张→指认心魔→回事实）先止血。",
        ]
    return json.dumps({
        "contextTokens": tokens,
        "level": level,
        "note": note,
        "advice": advice,
    }, ensure_ascii=False, indent=2)


@MCP.tool()
def xuanyuan_memory(action: str = "list", index: int = -1) -> str:
    """经验包记忆存取。action=list 列举全部；action=get 取指定序号(index)；action=clear 清空。"""
    s = _read_state()
    exps = s.get("experiences", [])
    if action == "clear":
        s["experiences"] = []
        s["experiencePacks"] = 0
        _write_state(s)
        return json.dumps({"cleared": True}, ensure_ascii=False)
    if action == "get":
        if 0 <= index < len(exps):
            return json.dumps(exps[index], ensure_ascii=False, indent=2)
        return json.dumps({"error": f"index 越界（共 {len(exps)} 条）"}, ensure_ascii=False)
    # default: list
    summary = [{
        "i": i,
        "method": e.get("method", "")[:80],
        "at": e.get("at"),
    } for i, e in enumerate(exps)]
    return json.dumps({
        "count": len(exps),
        "experiences": summary,
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    MCP.run()
