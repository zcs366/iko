"""
cost_consumer.py — IKO 成本记账模块

核心功能：
1. load_costs() — 加载成本数据
2. aggregate_costs(costs) — 按天/按模型/按任务聚合
3. generate_report(costs) — 生成成本报告
4. save_to_octopus(costs) — 保存到章鱼索引

设计原则：
- 消费 IO-S costs.jsonl
- 按天/按模型/按任务聚合
- 生成可搜索的成本报告
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# IO-S 成本数据目录
IO_S_DIR = Path.home() / ".io-s"
IO_S_COSTS = IO_S_DIR / "costs.jsonl"

# IKO 输出目录
IKO_DIR = Path.home() / "iko"
IKO_COSTS = IKO_DIR / "costs"


def ensure_dirs():
    """
    确保目录存在
    """
    IO_S_DIR.mkdir(parents=True, exist_ok=True)
    IKO_DIR.mkdir(parents=True, exist_ok=True)
    IKO_COSTS.mkdir(parents=True, exist_ok=True)


def load_costs(limit: int = 1000) -> list[dict]:
    """
    加载成本数据
    """
    ensure_dirs()
    
    if not IO_S_COSTS.exists():
        logger.info(f"Costs file not found: {IO_S_COSTS}")
        return []
    
    costs = []
    try:
        with open(IO_S_COSTS, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    cost = json.loads(line.strip())
                    costs.append(cost)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Failed to parse cost line: {e}")
                    continue
    except Exception as e:
        logger.warning(f"Failed to load costs: {e}")
    
    return costs[-limit:]


def aggregate_costs(costs: list[dict]) -> dict:
    """
    按天/按模型/按任务聚合成本
    """
    if not costs:
        return {}
    
    # 按天聚合
    by_day = defaultdict(lambda: {"total_tokens": 0, "total_cost": 0, "count": 0})
    
    # 按模型聚合
    by_model = defaultdict(lambda: {"total_tokens": 0, "total_cost": 0, "count": 0})
    
    # 按任务类型聚合
    by_task = defaultdict(lambda: {"total_tokens": 0, "total_cost": 0, "count": 0})
    
    for cost in costs:
        # 提取字段
        timestamp = cost.get("timestamp", "")
        model = cost.get("model", "unknown")
        task_type = cost.get("task_type", "unknown")
        tokens = cost.get("total_tokens", 0)
        cost_value = cost.get("cost", 0)
        
        # 按天聚合
        if timestamp:
            day = timestamp[:10]  # YYYY-MM-DD
            by_day[day]["total_tokens"] += tokens
            by_day[day]["total_cost"] += cost_value
            by_day[day]["count"] += 1
        
        # 按模型聚合
        by_model[model]["total_tokens"] += tokens
        by_model[model]["total_cost"] += cost_value
        by_model[model]["count"] += 1
        
        # 按任务类型聚合
        by_task[task_type]["total_tokens"] += tokens
        by_task[task_type]["total_cost"] += cost_value
        by_task[task_type]["count"] += 1
    
    return {
        "by_day": dict(by_day),
        "by_model": dict(by_model),
        "by_task": dict(by_task),
    }


def generate_report(costs: list[dict]) -> dict:
    """
    生成成本报告
    """
    if not costs:
        return {"total": 0, "summary": "No costs data"}
    
    # 聚合
    aggregated = aggregate_costs(costs)
    
    # 总计
    total_tokens = sum(c.get("total_tokens", 0) for c in costs)
    total_cost = sum(c.get("cost", 0) for c in costs)
    
    # 按模型统计
    by_model = aggregated.get("by_model", {})
    top_models = sorted(by_model.items(), key=lambda x: x[1]["total_cost"], reverse=True)[:5]
    
    # 按天统计
    by_day = aggregated.get("by_day", {})
    recent_days = sorted(by_day.items(), reverse=True)[:7]
    
    # 生成报告
    report = {
        "total_records": len(costs),
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "avg_tokens_per_record": total_tokens / len(costs) if costs else 0,
        "avg_cost_per_record": total_cost / len(costs) if costs else 0,
        "top_models": [
            {"model": m, "tokens": d["total_tokens"], "cost": d["total_cost"], "count": d["count"]}
            for m, d in top_models
        ],
        "recent_days": [
            {"day": d, "tokens": v["total_tokens"], "cost": v["total_cost"], "count": v["count"]}
            for d, v in recent_days
        ],
        "summary": f"共 {len(costs)} 条记录，总 token {total_tokens}，总成本 ${total_cost:.4f}",
    }
    
    return report


def save_to_octopus(costs: list[dict]) -> bool:
    """
    保存成本数据到章鱼索引
    """
    ensure_dirs()
    
    try:
        # 保存到 IKO costs 目录
        output_file = IKO_COSTS / f"costs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(costs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(costs)} costs to {output_file}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save costs: {e}")
        return False


def run_consumer(limit: int = 1000) -> dict:
    """
    运行成本消费流程
    """
    logger.info("Starting cost consumer...")
    
    # 加载成本
    costs = load_costs(limit)
    logger.info(f"Loaded {len(costs)} cost records")
    
    # 保存
    save_to_octopus(costs)
    
    # 生成报告
    report = generate_report(costs)
    
    return report


# ─── CLI ───

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python cost_consumer.py report [limit]  # 生成报告")
        print("  python cost_consumer.py list [limit]    # 列出成本")
        print("  python cost_consumer.py aggregate       # 聚合统计")
        sys.exit(0)
    
    cmd = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    if cmd == "report":
        report = run_consumer(limit)
        print("成本报告:")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    
    elif cmd == "list":
        costs = load_costs(limit)
        print(f"最近 {len(costs)} 条成本记录:")
        for i, cost in enumerate(costs[:20], 1):
            ts = cost.get("timestamp", "?")[:19]
            model = cost.get("model", "?")
            tokens = cost.get("total_tokens", 0)
            cost_value = cost.get("cost", 0)
            print(f"  {i}. [{ts}] {model}: {tokens} tokens, ${cost_value:.4f}")
    
    elif cmd == "aggregate":
        costs = load_costs(limit)
        aggregated = aggregate_costs(costs)
        
        print("聚合统计:")
        print("\n按模型:")
        for model, data in sorted(aggregated.get("by_model", {}).items(), 
                                   key=lambda x: x[1]["total_cost"], reverse=True):
            print(f"  {model}: {data['total_tokens']} tokens, ${data['total_cost']:.4f} ({data['count']} 次)")
        
        print("\n按天:")
        for day, data in sorted(aggregated.get("by_day", {}).items(), reverse=True)[:7]:
            print(f"  {day}: {data['total_tokens']} tokens, ${data['total_cost']:.4f} ({data['count']} 次)")
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
