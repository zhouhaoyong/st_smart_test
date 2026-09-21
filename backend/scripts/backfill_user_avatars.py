"""为历史用户补齐默认头像。

运行方式：在 backend 目录执行 `python scripts/backfill_user_avatars.py`。
仅处理头像为空且未软删除的用户，不覆盖用户已经上传的头像。
"""

import asyncio
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import or_, select

from db.session import AsyncSessionLocal, engine
from models.models import User
from utils.avatar import create_default_avatar


async def main() -> None:
    updated_count = 0
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(
                    User.is_deleted == False,
                    or_(User.avatar.is_(None), User.avatar == ""),
                )
            )
            users = result.scalars().all()
            for user in users:
                user.avatar = create_default_avatar(user.id, user.real_name)
                updated_count += 1
            await db.commit()
    finally:
        await engine.dispose()

    print(f"已补齐 {updated_count} 个用户的默认头像")


if __name__ == "__main__":
    asyncio.run(main())
