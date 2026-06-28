"""知识库冷启动种子数据生成脚本。

用途：
    在开发/部署初期，为指定目的地批量生成知识库条目，
    无需通过前端手动触发。

用法：
    # 在 FastAPIDemo 目录下执行
    python scripts/generate_knowledge.py --destination 东京

    # 指定类型
    python scripts/generate_knowledge.py --destination 东京 --types attraction food

    # 调整每种类型生成的条目数
    python scripts/generate_knowledge.py --destination 东京 --count 3

执行流程：
    1. 创建生成任务记录（pending）
    2. 同步执行生成流程（LLM 调用 + Embedding + 入库）
    3. 打印最终进度
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 将项目根目录（FastAPIDemo）加入 sys.path，使 app.* 可正常导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.services import knowledge_service  # noqa: E402

# 支持的条目类型，用于 argparse choices 校验
_VALID_TYPES = ("attraction", "food", "tip")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="知识库 AI 生成种子数据脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n  python scripts/generate_knowledge.py --destination 东京",
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="目的地名称（如：东京、巴黎、北京）",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=list(_VALID_TYPES),
        choices=_VALID_TYPES,
        help="生成类型列表，默认全部三种（attraction food tip）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="每种类型生成的条目数（默认 5）",
    )
    return parser.parse_args()


def main() -> None:
    """脚本主入口。"""
    args = parse_args()

    print(f"目的地：{args.destination}")
    print(f"类型：{args.types}")
    print(f"每种类型条目数：{args.count}")
    print("-" * 50)

    # 通过覆盖模块级常量来调整单类型条目数
    # （生产实现可改为函数参数传递，此处保持简洁）
    knowledge_service._PER_TYPE_COUNT = args.count  # noqa: SLF001

    # 创建独立 DB session
    with Session(engine) as db:
        # 1. 创建任务
        task = knowledge_service.create_task(
            db,
            destination=args.destination,
            types=args.types,
        )
        print(f"任务已创建：taskId={task.id}")
        print("开始生成知识库条目（可能需要数分钟）...")
        print("-" * 50)

        # 2. 同步执行生成（asyncio.run 创建事件循环）
        asyncio.run(knowledge_service.generate_for_destination(db, task.id))

        # 3. 刷新任务对象并打印结果
        db.refresh(task)
        print("-" * 50)
        print("生成完成")
        print(f"  状态：{task.status}")
        print(f"  总数：{task.total}")
        print(f"  成功：{task.success}")
        print(f"  失败：{task.failed}")
        if task.error_msg:
            print(f"  错误信息：{task.error_msg}")

    # 退出码：失败时返回 1
    sys.exit(0 if task.status == "completed" else 1)


if __name__ == "__main__":
    main()
