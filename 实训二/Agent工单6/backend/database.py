"""
数据库连接和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import os

from models.database import Base


# 数据库URL配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/workorders.db")

# 创建数据库引擎
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite特定配置
        echo=False
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_database():
    """初始化数据库，创建所有表"""
    # 确保data目录存在
    os.makedirs("./data", exist_ok=True)

    # 创建所有表
    Base.metadata.create_all(bind=engine)
    print("数据库初始化完成")


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖项
    用于FastAPI的依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器
    用于非FastAPI的场景
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_database():
    """关闭数据库连接"""
    engine.dispose()
    print("数据库连接已关闭")
