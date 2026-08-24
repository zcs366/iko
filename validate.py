#!/usr/bin/env python3
"""validate.py — IKO 八触须输出校验工具 (IDC Day 3指令)

检查一个产出物是否：
1. 包含正确的八触须 v2 格式元数据头
2. 覆盖了指定触须
3. 元数据头字段格式正确

用法：
    python3 validate.py <产出物文件路径>
    python3 validate.py <产出物文件路径> --quiet   # 只输出 pass/fail
    python3 validate.py --list-checks               # 列出所有检查项
"""

import re
import sys
import yaml
from pathlib import Path

# ═══════════════════════════════════════
# 八触须v2格式检查项
# ═══════════════════════════════════════

VALID_TYPES = {"techdoc", "memo", "analysis", "code", "design", "report"}
VALID_SYSTEMS = {"isa", "ios", "isn", "iko"}
VALID_TENTACLES = set(range(1, 9))  # 1-8
VALID_SEVERITIES = {"warn", "require"}


def check_yaml_header(filepath: str) -> dict:
    """检查 YAML 元数据头是否存在且格式正确。
    
    Returns:
        {"ok": True/False, "errors": [str], "header": dict or None}
    """
    content = Path(filepath).read_text(encoding="utf-8")
    result = {"ok": True, "errors": [], "warnings": [], "header": None}
    
    # 必须包含 --- 分隔符
    if not content.startswith("---"):
        result["ok"] = False
        result["errors"].append("缺失 YAML 元数据头（必须以 --- 开头）")
        return result
    
    # 找到第二个 ---
    second = content.find("\n---", 3)
    if second == -1:
        result["ok"] = False
        result["errors"].append("YAML 元数据头未正确闭合（缺少第二个 ---）")
        return result
    
    yaml_text = content[3:second]
    try:
        header = yaml.safe_load(yaml_text)
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"YAML 解析失败: {e}")
        return result
    
    if not isinstance(header, dict):
        result["ok"] = False
        result["errors"].append("YAML 头不是字典格式")
        return result
    
    result["header"] = header
    
    # ── 必填字段检查 ──
    for field in ("type", "eight_tentacles", "created", "author_system"):
        if field not in header:
            result["ok"] = False
            result["errors"].append(f"缺少必填字段: {field}")
    
    # ── type 有效性 ──
    t = header.get("type")
    if t and t not in VALID_TYPES:
        result["warnings"].append(f"type '{t}' 不在标准类型中: {VALID_TYPES}")
    
    # ── author_system 有效性 ──
    s = header.get("author_system")
    if s and s not in VALID_SYSTEMS:
        result["warnings"].append(f"author_system '{s}' 不在标准标识中: {VALID_SYSTEMS}")
    
    # ── eight_tentacles 格式 ──
    tentacles = header.get("eight_tentacles", [])
    if isinstance(tentacles, list):
        for t in tentacles:
            if t not in VALID_TENTACLES:
                result["warnings"].append(f"触须 {t} 超出范围 1-8")
    else:
        result["warnings"].append("eight_tentacles 应为列表格式")
    
    # ── created 格式 ──
    created = header.get("created", "")
    if created and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(created)):
        result["warnings"].append(f"created 时间格式非 ISO 8601: {created}")
    
    # ── governance_context 格式 ──
    gc = header.get("governance_context")
    if gc and isinstance(gc, dict):
        if "trace_id" in gc and not gc["trace_id"]:
            result["warnings"].append("governance_context.trace_id 为空")
        if "verify_status" in gc and gc["verify_status"] not in ("passed", "failed", "warn"):
            result["warnings"].append(f"verify_status '{gc['verify_status']}' 非标准值")
    
    return result


def check_content_exists(filepath: str) -> dict:
    """检查文件是否有正文内容（YAML头之后）。"""
    content = Path(filepath).read_text(encoding="utf-8")
    second = content.find("\n---", 3)
    body = content[second + 4:].strip() if second != -1 else content.strip()
    result = {"ok": bool(body), "content_length": len(body)}
    if not body:
        result["error"] = "文件缺少正文内容（仅有 YAML 元数据头）"
    return result


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def validate(filepath: str) -> dict:
    """对单个文件执行全部校验。"""
    report = {"file": filepath, "ok": True, "checks": []}
    
    c1 = check_yaml_header(filepath)
    report["checks"].append({"name": "YAML元数据头", **c1})
    if not c1["ok"]:
        report["ok"] = False
    
    c2 = check_content_exists(filepath)
    report["checks"].append({"name": "正文内容", **c2})
    if not c2["ok"]:
        report["ok"] = False
    
    return report


if __name__ == "__main__":
    if "--list-checks" in sys.argv:
        print("IKO validate.py 检查项:")
        print("  1. YAML元数据头存在性")
        print("  2. 必填字段: type, eight_tentacles, created, author_system")
        print("  3. type 值有效性")
        print("  4. author_system 值有效性")
        print("  5. eight_tentacles 格式和范围")
        print("  6. created 时间格式")
        print("  7. governance_context 格式")
        print("  8. 正文内容存在性")
        sys.exit(0)
    
    quiet = "--quiet" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("--")]
    
    if not targets:
        print("用法: python3 validate.py <文件路径> [--quiet] [--list-checks]")
        sys.exit(1)
    
    all_ok = True
    for fp in targets:
        report = validate(fp)
        if quiet:
            status = "PASS" if report["ok"] else "FAIL"
            print(f"{status}: {fp}")
        else:
            print(f"\n{'='*50}")
            print(f"文件: {fp}")
            print(f"{'='*50}")
            for c in report["checks"]:
                icon = "✅" if c.get("ok") else "❌"
                print(f"  {icon} {c['name']}")
                for e in c.get("errors", []):
                    print(f"     🔴 {e}")
                for w in c.get("warnings", []):
                    print(f"     🟡 {w}")
            print(f"\n总体: {'✅ PASS' if report['ok'] else '❌ FAIL'}")
        if not report["ok"]:
            all_ok = False
    
    sys.exit(0 if all_ok else 1)
