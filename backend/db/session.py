"""
Database connection and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import settings

# 创建异步数据库引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_recycle=3600,  # 连接回收时间（秒），小于 MySQL wait_timeout，防止空闲连接断开
    pool_pre_ping=True,  # 使用前先 ping 检测连接是否存活
    pool_size=10,        # 连接池大小
    max_overflow=20,     # 超出 pool_size 后最多再创建的连接数
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 基础模型类
Base = declarative_base()


async def get_db():
    """获取数据库会话的依赖项"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()