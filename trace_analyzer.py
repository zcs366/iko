"""
trace_analyzer.py — IO-S trace 自分析管线

核心功能：
1. load_traces() — 加载 trace 数据
2. analyze_traces(traces) — 分析 trace（成功率/延迟/token/热点工具）
3. generate_report(analysis) — 生成分析报告
4. save_report(report) — 保存报告到章鱼索引

设计原则：
- 读 ~/.io-s/traces/*.jsonl
- 按维度分析：工具/模型/任务/时间
- 生成可搜索的分析报告
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# IO-S traces 目录
IO_S_DIR = Path.home() / ".io-s"
IO_S_TRACES = IO_S_DIR / "traces"

# IKO 输出目录
IKO_DIR = Path.home() / "iko"
IKO_REPORTS = IKO_DIR / "reports"


def ensure_dirs():
    """
    确保目录存在
    """
    IO_S_TRACES.mkdir(parents=True, exist_ok=True)
    IKO_DIR.mkdir(parents=True, exist_ok=True)
    IKO_REPORTS.mkdir(parents=True, exist_ok=True)


def load_traces(limit: int = 1000) -> list[dict]:
    """
    加载 trace 数据
    """
    ensure_dirs()
    
    traces = []
    
    # 遍历 traces 目录下的所有 JSONL 文件
    for trace_file in sorted(IO_S_TRACES.glob("*.jsonl"), reverse=True):
        if len(traces) >= limit:
            break
        
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        trace = json.loads(line.strip())
                        traces.append(trace)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.debug(f"Failed to parse trace line: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Failed to load trace file {trace_file}: {e}")
    
    return traces[-limit:]


def analyze_traces(traces: list[dict]) -> dict:
    """
    分析 trace 数据
    """
    if not traces:
        return {"total": 0, "summary": "No traces to analyze"}
    
    # 统计维度
    by_tool = defaultdict(lambda: {"count": 0, "success": 0, "fail": 0, "total_duration": 0})
    by_model = defaultdict(lambda: {"count": 0, "total_tokens": 0, "total_duration": 0})
    by_type = Counter()
    by_verdict = Counter()
    
    total_duration = 0
    total_tokens = 0
    
    for trace in traces:
        # 基本字段
        trace_type = trace.get("type", "unknown")
        verdict = trace.get("verdict", "unknown")
        tool_name = trace.get("tool_name", "")
        model = trace.get("model", "unknown")
        duration = trace.get("duration_ms", 0)
        tokens = trace.get("token_usage", {}).get("total", 0)
        
        # 按类型统计
        by_type[trace_type] += 1
        
        # 按结果统计
        by_verdict[verdict] += 1
        
        # 按工具统计
        if tool_name:
            by_tool[tool_name]["count"] += 1
            if verdict == "pass":
                by_tool[tool_name]["success"] += 1
            else:
                by_tool[tool_name]["fail"] += 1
            by_tool[tool_name]["total_duration"] += duration
        
        # 按模型统计
        by_model[model]["count"] += 1
        by_model[model]["total_tokens"] += tokens
        by_model[model]["total_duration"] += duration
        
        # 总计
        total_duration += duration
        total_tokens += tokens
    
    # 计算成功率
    total = len(traces)
    pass_count = by_verdict.get("pass", 0)
    success_rate = pass_count / total if total > 0 else 0
    
    # 热点工具（按使用频率排序）
    hot_tools = sorted(by_tool.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    
    # 慢工具（按平均延迟排序）
    slow_tools = []
    for tool, data in by_tool.items():
        if data["count"] > 0:
            avg_duration = data["total_duration"] / data["count"]
            slow_tools.append({"tool": tool, "avg_duration": avg_duration, "count": data["count"]})
    slow_tools.sort(key=lambda x: x["avg_duration"], reverse=True)
    slow_tools = slow_tools[:10]
    
    # 生成分析结果
    analysis = {
        "total": total,
        "success_rate": success_rate,
        "pass_count": pass_count,
        "fail_count": total - pass_count,
        "total_duration_ms": total_duration,
        "avg_duration_ms": total_duration / total if total > 0 else 0,
        "total_tokens": total_tokens,
        "avg_tokens": total_tokens / total if total > 0 else 0,
        "by_type": dict(by_type),
        "by_verdict": dict(by_verdict),
        "hot_tools": [
            {"tool": t, "count": d["count"], "success_rate": d["success"] / d["count"] if d["count"] > 0 else 0}
            for t, d in hot_tools
        ],
        "slow_tools": slow_tools,
        "by_model": [
            {"model": m, "count": d["count"], "total_tokens": d["total_tokens"], "avg_tokens": d["total_tokens"] / d["count"] if d["count"] > 0 else 0}
            for m, d in sorted(by_model.items(), key=lambda x: x[1]["count"], reverse=True)
        ],
    }
    
    return analysis


def generate_report(analysis: dict) -> str:
    """
    生成 Markdown 格式的分析报告
    """
    if analysis.get("total", 0) == 0:
        return "# Trace 分析报告\n\n无 trace 数据。"
    
    report = f"""# Trace 分析报告

> 生成时间: {datetime.now(timezone.utc).isoformat()[:19]}

## 概览

| 指标 | 值 |
|------|-----|
| 总 trace 数 | {analysis['total']} |
| 成功率 | {analysis['success_rate']:.1%} |
| 通过数 | {analysis['pass_count']} |
| 失败数 | {analysis['fail_count']} |
| 总时长 | {analysis['total_duration_ms'] / 1000:.1f}s |
| 平均时长 | {analysis['avg_duration_ms']:.0f}ms |
| 总 token | {analysis['total_tokens']:,} |
| 平均 token | {analysis['avg_tokens']:.0f} |

## 按类型分布

| 类型 | 数量 |
|------|------|
"""
    for typ, count in sorted(analysis.get("by_type", {}).items(), key=lambda x: x[1], reverse=True):
        report += f"| {typ} | {count} |\n"
    
    report += f"""
## 热点工具（Top 10）

| 工具 | 使用次数 | 成功率 |
|------|----------|--------|
"""
    for item in analysis.get("hot_tools", []):
        report += f"| {item['tool']} | {item['count']} | {item['success_rate']:.1%} |\n"
    
    report += f"""
## 慢工具（Top 10）

| 工具 | 平均延迟 | 使用次数 |
|------|----------|----------|
"""
    for item in analysis.get("slow_tools", []):
        report += f"| {item['tool']} | {item['avg_duration']:.0f}ms | {item['count']} |\n"
    
    report += f"""
## 模型使用

| 模型 | 调用次数 | 总 token | 平均 token |
|------|----------|----------|------------|
"""
    for item in analysis.get("by_model", []):
        report += f"| {item['model']} | {item['count']} | {item['total_tokens']:,} | {item['avg_tokens']:.0f} |\n"
    
    return report


def save_report(report: str, analysis: dict) -> bool:
    """
    保存报告到章鱼索引
    """
    ensure_dirs()
    
    try:
        # 保存 Markdown 报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = IKO_REPORTS / f"trace_report_{timestamp}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        # 保存 JSON 分析结果
        analysis_file = IKO_REPORTS / f"trace_analysis_{timestamp}.json"
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved trace report to {report_file}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save report: {e}")
        return False


def run_analyzer(limit: int = 1000) -> dict:
    """
    运行 trace 分析流程
    """
    logger.info("Starting trace analyzer...")
    
    # 加载 trace
    traces = load_traces(limit)
    logger.info(f"Loaded {len(traces)} traces")
    
    # 分析
    analysis = analyze_traces(traces)
    logger.info(f"Analysis complete: {analysis.get('total', 0)} traces")
    
    # 生成报告
    report = generate_report(analysis)
    
    # 保存
    save_report(report, analysis)
    
    return {
        "analysis": analysis,
        "report_file": str(IKO_REPORTS / f"trace_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"),
    }


# ─── CLI ───

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python trace_analyzer.py analyze [limit]  # 分析 trace")
        print("  python trace_analyzer.py report [limit]   # 生成报告")
        print("  python trace_analyzer.py summary [limit]  # 显示摘要")
        sys.exit(0)
    
    cmd = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    if cmd == "analyze":
        result = run_analyzer(limit)
        print("分析完成:")
        print(f"  报告文件: {result['report_file']}")
        print(f"  总 trace: {result['analysis'].get('total', 0)}")
        print(f"  成功率: {result['analysis'].get('success_rate', 0):.1%}")
    
    elif cmd == "report":
        traces = load_traces(limit)
        analysis = analyze_traces(traces)
        report = generate_report(analysis)
        print(report)
    
    elif cmd == "summary":
        traces = load_traces(limit)
        analysis = analyze_traces(traces)
        
        print(f"Trace 分析摘要:")
        print(f"  总数: {analysis.get('total', 0)}")
        print(f"  成功率: {analysis.get('success_rate', 0):.1%}")
        print(f"  总时长: {analysis.get('total_duration_ms', 0) / 1000:.1f}s")
        print(f"  总 token: {analysis.get('total_tokens', 0):,}")
        print(f"\n  热点工具:")
        for item in analysis.get("hot_tools", [])[:5]:
            print(f"    - {item['tool']}: {item['count']} 次 (成功率 {item['success_rate']:.1%})")
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
