"""数据库初始化与数据迁移唯一入口。

启动流程必须先执行本文件；本文件失败时，调用方不得继续启动 Web 服务。

当前项目没有待执行的一次性迁移，因此本文件只负责：
- 创建数据库中缺失的模型表；
- 初始化默认消息模板；
- 保留后续表结构和数据迁移的集中占位区。

后续发生表结构或历史数据变化时，必须先修改模型，再在本文件的迁移占位区
补充经过评审、可重复执行且失败可诊断的迁移逻辑。禁止把一次性迁移 SQL
散落到业务代码、接口代码或临时脚本中。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings
from db.session import AsyncSessionLocal
from models.ai_models import (  # noqa: F401 - 确保 AI 相关表注册到 Base.metadata
    AiModel,
    AiModelDetectionLog,
    AiPlatformQuotaSetting,
    AiUsageLog,
    AiUserModelQuota,
)
from models.audit_log import AuditLog  # noqa: F401 - 确保审计表注册到 Base.metadata
from models.models import Base
from services.message_service import seed_default_message_templates


# ---------------------------------------------------------------------------
# 数据库迁移占位区
#
# 当前没有待执行迁移，保持为空。
#
# 后续变更规则：
# - 新增数据表：修改模型，由 Base.metadata.create_all 创建缺失表；
# - 新增可空字段：确认无需历史数据后，可在这里补充安全迁移；
# - 非空字段、字段修改、字段重命名、索引、外键和数据回填：
#   必须在这里写明迁移目标、执行条件和幂等 SQL；
# - 删除表或字段：默认禁止，必须经过评审、检查依赖并显式放行；
# - 迁移失败必须抛出异常，阻止应用继续启动；
# - 不得猜测历史数据，也不得让用户手动修改数据库。
# ---------------------------------------------------------------------------

_PENDING_MIGRATIONS: tuple[str, ...] = ()


async def _apply_pending_migrations(conn) -> None:
    """执行后续登记在本文件中的迁移；当前无迁移。"""
    # 后续有实际表结构或数据变化时，在这里补充经过评审的幂等迁移逻辑。
    return


async def init_db() -> None:
    print("开始初始化数据库。")
    engine = create_async_engine(settings.DATABASE_URL)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_pending_migrations(conn)
            print("数据库表结构初始化完成。")

        async with AsyncSessionLocal() as db:
            await seed_default_message_templates(db)
            print("默认消息模板初始化完成。")

        print("数据库初始化完成。")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
