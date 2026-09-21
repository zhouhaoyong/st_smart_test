"""
创建超级管理员账号

用法:
    python create_superadmin.py --phone 13800000000 --password YourPwd123 --real-name 张三
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from core.config import settings
from models.models import User
from core.security import get_password_hash
from core.permissions import normalize_role_flags
from core.user_validation import validate_password, validate_phone, validate_real_name
from utils.avatar import create_default_avatar

_engine = create_async_engine(settings.DATABASE_URL, echo=False)
_AsyncSessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def create_superadmin(phone: str, password: str, real_name: str = "超级管理员"):
    try:
        phone = validate_phone(phone)
        password = validate_password(password)
        real_name = validate_real_name(real_name)
    except ValueError as exc:
        print(f"错误: {exc}")
        sys.exit(1)

    async with _AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.phone == phone)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.is_deleted:
                print(f"错误: 手机号 {phone} 已被删除账号占用，请更换手机号")
                sys.exit(1)
            if not existing.avatar:
                existing.avatar = create_default_avatar(existing.id, existing.real_name)
            if existing.is_superuser:
                _, existing.is_manager = normalize_role_flags(
                    existing.is_superuser,
                    existing.is_manager,
                )
                await db.commit()
                print(f"用户 {phone} 已经是超级管理员，无需重复创建")
                return
            existing.is_superuser, existing.is_manager = normalize_role_flags(True, False)
            existing.is_active = True
            existing.password = get_password_hash(password)
            await db.commit()
            print(f"已将用户 {phone} 升级为超级管理员（密码已更新）")
            return

        # 检查真实姓名是否已被占用
        result = await db.execute(
            select(User).where(User.real_name == real_name)
        )
        if result.scalar_one_or_none():
            print(f"错误: 真实姓名「{real_name}」已被使用，请更换")
            sys.exit(1)

        user = User(
            phone=phone,
            password=get_password_hash(password),
            real_name=real_name,
            gender=3,
            department=1,
            is_active=True,
            is_superuser=True,
            is_manager=False,
        )
        db.add(user)
        try:
            await db.flush()
            user.avatar = create_default_avatar(user.id, user.real_name)
            await db.commit()
        except IntegrityError as e:
            msg = str(e).lower()
            if 'phone' in msg:
                print(f"错误: 手机号 {phone} 已被注册")
            elif 'real_name' in msg:
                print(f"错误: 真实姓名「{real_name}」已被使用，请更换")
            else:
                print(f"错误: 数据冲突，{e}")
            sys.exit(1)
        print(f"超级管理员创建成功: {phone} ({real_name})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建超级管理员账号")
    parser.add_argument("--phone", required=True, help="手机号（11位）")
    parser.add_argument("--password", required=True, help="密码（至少6位，需包含大小写字母）")
    parser.add_argument("--real-name", required=True, help="真实姓名（2-20个中文，不可重复）")
    args = parser.parse_args()

    asyncio.run(create_superadmin(args.phone, args.password, args.real_name))
