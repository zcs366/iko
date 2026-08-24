"""
trace_consumer.py — IKO 结构化 trace 消费模块

核心功能：
1. consume_trace(trace_event) — 消费单条 trace 事件
2. consume_batch(trace_events) — 批量消费 trace 事件
3. save_to_octopus(trace) — 保存到章鱼索引
4. generate_report(traces) — 生成 trace 报告

设计原则：
- 消费 IO-S trace 信号
- 结构化提取：每个 trace 事件打上标签
- 保存到章鱼索引，可搜索
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# IO-S trace 信号目录
IO_S_SIGNALS = Path.home() / ".io-s" / "signals"
IO_S_TRACES = Path.home() / ".io-s" / "traces"

# IKO 输出目录
IKO_DIR = Path.home() / "iko"
IKO_TRACES = IKO_DIR / "traces"


def ensure_dirs():
    """
    确保目录存在
    """
    IO_S_SIGNALS.mkdir(parents=True, exist_ok=True)
    IO_S_TRACES.mkdir(parents=True, exist_ok=True)
    IKO_DIR.mkdir(parents=True, exist_ok=True)
    IKO_TRACES.mkdir(parents=True, exist_ok=True)


def load_traces_from_io_s(limit: int = 100) -> list[dict]:
    """
    从 IO-S 加载 trace 事件
    """
    ensure_dirs()
    
    traces = []
    
    # 从 traces 目录加载
    for trace_file in sorted(IO_S_TRACES.glob("*.json"), reverse=True):
        if len(traces) >= limit:
            break
        
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, list):
                traces.extend(data)
            else:
                traces.append(data)
        except Exception as e:
            logger.warning(f"Failed to load trace {trace_file}: {e}")
    
    # 从 signals 目录加载
    for signal_file in sorted(IO_S_SIGNALS.glob("*.json"), reverse=True):
        if len(traces) >= limit:
            break
        
        try:
            with open(signal_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 只加载 trace 类型的信号（可通过环境变量扩展）
            TRACE_TYPES = os.environ.get("IKO_TRACE_TYPES", "verify,hindsight,checkpoint").split(",")
            if data.get("type") in TRACE_TYPES:
                traces.append(data)
        except Exception as e:
            logger.warning(f"Failed to load signal {signal_file}: {e}")
    
    return traces[:limit]


def consume_trace(trace_event: dict) -> dict:
    """
    消费单条 trace 事件
    
    Args:
        trace_event: trace 事件字典
    
    Returns:
        结构化的 trace 记录
    """
    # 提取关键信息
    record = {
        "timestamp": trace_event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "type": trace_event.get("type", "unknown"),
        "source": trace_event.get("source", "io-s"),
        "session_id": trace_event.get("session_id", ""),
        "tool_name": trace_event.get("tool_name", ""),
        "verdict": trace_event.get("verdict", ""),
        "duration_ms": trace_event.get("duration_ms", 0),
        "token_usage": trace_event.get("token_usage", {}),
        "raw": trace_event,
    }
    
    # 添加标签
    record["tags"] = extract_tags(record)
    
    return record


def extract_tags(record: dict) -> list[str]:
    """
    从 trace 记录中提取标签
    """
    tags = []
    
    # 类型标签
    trace_type = record.get("type", "")
    if trace_type:
        tags.append(f"type:{trace_type}")
    
    # 工具标签
    tool_name = record.get("tool_name", "")
    if tool_name:
        tags.append(f"tool:{tool_name}")
    
    # 结果标签
    verdict = record.get("verdict", "")
    if verdict:
        tags.append(f"verdict:{verdict}")
    
    return tags


def consume_batch(trace_events: list[dict]) -> list[dict]:
    """
    批量消费 trace 事件
    """
    return [consume_trace(event) for event in trace_events]


def save_to_octopus(traces: list[dict]) -> bool:
    """
    保存 trace 到章鱼索引
    
    Args:
        traces: trace 记录列表
    
    Returns:
        是否成功
    """
    ensure_dirs()
    
    try:
        # 保存到 IKO traces 目录
        output_file = IKO_TRACES / f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(traces, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(traces)} traces to {output_file}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save traces: {e}")
        return False


def generate_report(traces: list[dict]) -> dict:
    """
    生成 trace 报告
    """
    if not traces:
        return {"total": 0, "summary": "No traces"}
    
    # 统计
    total = len(traces)
    by_type = {}
    by_verdict = {}
    total_duration = 0
    total_tokens = 0
    
    for trace in traces:
        # 按类型统计
        trace_type = trace.get("type", "unknown")
        by_type[trace_type] = by_type.get(trace_type, 0) + 1
        
        # 按结果统计
        verdict = trace.get("verdict", "unknown")
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        
        # 总时长
        total_duration += trace.get("duration_ms", 0)
        
        # 总 token
        token_usage = trace.get("token_usage", {})
        total_tokens += token_usage.get("total", 0)
    
    # 生成报告
    report = {
        "total": total,
        "by_type": by_type,
        "by_verdict": by_verdict,
        "total_duration_ms": total_duration,
        "avg_duration_ms": total_duration / total if total > 0 else 0,
        "total_tokens": total_tokens,
        "avg_tokens": total_tokens / total if total > 0 else 0,
        "summary": f"共 {total} 条 trace，通过 {by_verdict.get('pass', 0)} 条，失败 {by_verdict.get('fail', 0)} 条",
    }
    
    return report


def run_consumer(limit: int = 100) -> dict:
    """
    运行 trace 消费流程
    """
    logger.info("Starting trace consumer...")
    
    # 加载 trace
    raw_traces = load_traces_from_io_s(limit)
    logger.info(f"Loaded {len(raw_traces)} raw traces")
    
    # 消费
    traces = consume_batch(raw_traces)
    logger.info(f"Consumed {len(traces)} traces")
    
    # 保存
    save_to_octopus(traces)
    
    # 生成报告
    report = generate_report(traces)
    
    return report


# ─── CLI ───

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python trace_consumer.py consume [limit]  # 消费 trace")
        print("  python trace_consumer.py report [limit]   # 生成报告")
        print("  python trace_consumer.py list [limit]     # 列出 trace")
        sys.exit(0)
    
    cmd = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    if cmd == "consume":
        report = run_consumer(limit)
        print("消费完成:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    
    elif cmd == "report":
        raw_traces = load_traces_from_io_s(limit)
        traces = consume_batch(raw_traces)
        report = generate_report(traces)
        
        print("Trace 报告:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    
    elif cmd == "list":
        raw_traces = load_traces_from_io_s(limit)
        traces = consume_batch(raw_traces)
        
        print(f"最近 {len(traces)} 条 trace:")
        for i, trace in enumerate(traces[:20], 1):
            ts = trace.get("timestamp", "?")[:19]
            typ = trace.get("type", "?")
            tool = trace.get("tool_name", "?")
            verdict = trace.get("verdict", "?")
            print(f"  {i}. [{ts}] {typ} ({tool}): {verdict}")
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
