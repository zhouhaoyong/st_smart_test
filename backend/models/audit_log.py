"""
Audit Log model for tracking user operations
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base
from datetime import datetime
from core.timezone import beijing_now
from sqlalchemy import Index


class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index('inx_user_id', 'user_id'),
        Index('inx_module', 'module'),
        Index('inx_created_at', 'created_at'),
        {'comment': '审计日志表'}
    )
    
    # 必填字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='id')
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment='操作用户ID')
    user_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='操作用户姓名')
    
    # 操作信息
    module: Mapped[str] = mapped_column(String(50), nullable=False, comment='操作模块: user/project/interface/testcase等')
    operation: Mapped[str] = mapped_column(String(20), nullable=False, comment='操作类型: create/update/delete')
    target_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='操作目标ID')
    target_name: Mapped[str] = mapped_column(String(200), nullable=True, comment='操作目标名称')
    
    # 详细信息
    description: Mapped[str] = mapped_column(Text, nullable=True, comment='操作描述')
    details: Mapped[dict] = mapped_column(JSON, nullable=True, comment='操作详情(JSON)')
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True, comment='IP地址')
    
    # 审计字段
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment='软删除标记')
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<AuditLog(id={self.id}, user={self.user_name}, module={self.module}, operation={self.operation})>'

