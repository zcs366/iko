"""
health_dashboard.py — IKO 健康 Dashboard 模块

核心功能：
1. collect_health_data() — 收集四体健康数据
2. generate_dashboard() — 生成 dashboard 报告
3. save_to_octopus() — 保存到章鱼索引

设计原则：
- 章鱼可搜索的治理健康报告
- 任务成功率、延迟、token 成本可视化
- 四体（ISA/IO-S/ISN/IKO）健康状态
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 四体目录
ISA_DIR = Path.home() / ".hermes" / "jiak"
IO_S_DIR = Path.home() / ".io-s"
ISN_DIR = Path.home() / "isn"
IKO_DIR = Path.home() / "iko"

# IKO 输出目录
IKO_DASHBOARD = IKO_DIR / "dashboard"


def ensure_dirs():
    """
    确保目录存在
    """
    IO_S_DIR.mkdir(parents=True, exist_ok=True)
    IKO_DIR.mkdir(parents=True, exist_ok=True)
    IKO_DASHBOARD.mkdir(parents=True, exist_ok=True)


def collect_isa_health() -> dict:
    """
    收集 ISA 健康数据
    """
    recall_path = ISA_DIR / "RECALL.jsonl"
    cards_dir = ISA_DIR / "cards"
    
    recall_lines = 0
    if recall_path.exists():
        try:
            with open(recall_path, "r", encoding="utf-8") as f:
                recall_lines = sum(1 for _ in f)
        except (OSError, IOError) as e:
            logger.debug(f"Failed to read RECALL: {e}")
    
    cards_count = len(list(cards_dir.glob("*.json"))) if cards_dir.exists() else 0
    
    return {
        "recall_lines": recall_lines,
        "cards_count": cards_count,
        "status": "healthy" if recall_lines > 0 else "degraded",
    }


def collect_io_s_health() -> dict:
    """
    收集 IO-S 健康数据
    """
    signals_dir = IO_S_DIR / "signals"
    checkpoints_dir = IO_S_DIR / "checkpoints"
    
    signals_count = len(list(signals_dir.glob("*.json"))) if signals_dir.exists() else 0
    checkpoints_count = len(list(checkpoints_dir.glob("*.json"))) if checkpoints_dir.exists() else 0
    
    return {
        "signals_count": signals_count,
        "checkpoints_count": checkpoints_count,
        "status": "healthy" if signals_count > 0 else "degraded",
    }


def collect_isn_health() -> dict:
    """
    收集 ISN 健康数据
    """
    index_path = ISN_DIR / "store" / "index.yaml"
    
    skills_count = 0
    if index_path.exists():
        try:
            import yaml
            with open(index_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            skills_count = len(data.get("skills", []))
        except:
            pass
    
    return {
        "skills_count": skills_count,
        "status": "healthy" if skills_count > 0 else "degraded",
    }


def collect_iko_health() -> dict:
    """
    收集 IKO 健康数据
    """
    traces_dir = IKO_DIR / "traces"
    costs_dir = IKO_DIR / "costs"
    dashboard_dir = IKO_DIR / "dashboard"
    
    traces_count = len(list(traces_dir.glob("*.json"))) if traces_dir.exists() else 0
    costs_count = len(list(costs_dir.glob("*.json"))) if costs_dir.exists() else 0
    dashboard_count = len(list(dashboard_dir.glob("*.json"))) if dashboard_dir.exists() else 0
    
    return {
        "traces_count": traces_count,
        "costs_count": costs_count,
        "dashboard_count": dashboard_count,
        "status": "healthy",
    }


def collect_health_data() -> dict:
    """
    收集四体健康数据
    """
    return {
        "isa": collect_isa_health(),
        "io_s": collect_io_s_health(),
        "isn": collect_isn_health(),
        "iko": collect_iko_health(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_dashboard(health_data: dict = None) -> dict:
    """
    生成 dashboard 报告
    """
    if health_data is None:
        health_data = collect_health_data()
    
    # 计算总体健康状态
    systems = ["isa", "io_s", "isn", "iko"]
    healthy_count = sum(1 for s in systems if health_data.get(s, {}).get("status") == "healthy")
    total_count = len(systems)
    
    overall_status = "healthy" if healthy_count == total_count else "degraded"
    
    # 生成报告
    dashboard = {
        "overall_status": overall_status,
        "healthy_systems": healthy_count,
        "total_systems": total_count,
        "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0,
        "systems": health_data,
        "summary": f"四体健康状态: {healthy_count}/{total_count} 正常 ({health_data.get('timestamp', '')})",
    }
    
    return dashboard


def save_to_octopus(dashboard: dict) -> bool:
    """
    保存 dashboard 到章鱼索引
    """
    ensure_dirs()
    
    try:
        output_file = IKO_DASHBOARD / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved dashboard to {output_file}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save dashboard: {e}")
        return False


def run_dashboard() -> dict:
    """
    运行 dashboard 生成流程
    """
    logger.info("Starting health dashboard...")
    
    # 收集健康数据
    health_data = collect_health_data()
    logger.info(f"Collected health data: {len(health_data)} systems")
    
    # 生成 dashboard
    dashboard = generate_dashboard(health_data)
    
    # 保存
    save_to_octopus(dashboard)
    
    return dashboard


# ─── CLI ───

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python health_dashboard.py status    # 显示健康状态")
        print("  python health_dashboard.py generate  # 生成 dashboard")
        print("  python health_dashboard.py json      # 输出 JSON")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        health_data = collect_health_data()
        dashboard = generate_dashboard(health_data)
        
        print(f"四体健康状态: {dashboard['overall_status']}")
        print(f"健康系统: {dashboard['healthy_systems']}/{dashboard['total_systems']}")
        print(f"健康度: {dashboard['health_percentage']:.0f}%")
        print("\n各系统:")
        for system, data in health_data.items():
            if system == "timestamp":
                continue
            status = data.get("status", "?")
            emoji = "✅" if status == "healthy" else "⚠️"
            print(f"  {emoji} {system}: {status}")
    
    elif cmd == "generate":
        dashboard = run_dashboard()
        print("Dashboard 生成完成:")
        print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    
    elif cmd == "json":
        health_data = collect_health_data()
        dashboard = generate_dashboard(health_data)
        print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
