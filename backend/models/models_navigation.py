"""
Database models for the API Auto Test Platform
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base
from datetime import datetime
from core.timezone import beijing_now
from sqlalchemy import Index


class MessageChannel(Base):
    """平台统一消息渠道"""
    __tablename__ = "message_channels"
    __table_args__ = {'comment': '消息渠道表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='渠道名称')
    channel_type = Column(String(50), nullable=False, default="dingtalk", comment="消息渠道类型：dingtalk/feishu/wecom/webhook")
    webhook_url = Column(String(500), nullable=False, comment='Webhook地址')
    secret = Column(String(255), nullable=True, comment='签名密钥')
    keyword = Column(String(100), nullable=True, comment='触发关键词')
    group_name = Column(String(100), nullable=True, comment='群组名称')
    is_active = Column(Boolean, default=True, comment='是否启用')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    creator = relationship("User")


class MessageTemplate(Base):
    """平台统一消息模板"""
    __tablename__ = "message_templates"
    __table_args__ = {'comment': '消息模板表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='模板名称')
    module = Column(String(50), nullable=False, comment="所属模块标识，例如 api_test")
    event_type = Column(String(50), nullable=False, comment="消息事件类型：execution_report/daily_report/event_push")
    content = Column(Text, nullable=False, comment='模板内容')
    variables = Column(JSON, default=list, comment='模板变量列表')
    is_default = Column(Boolean, default=False, comment='是否默认模板')
    is_active = Column(Boolean, default=True, comment='是否启用')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    creator = relationship("User")


class MessageBinding(Base):
    """平台统一消息绑定：模块对象在某事件下使用哪些渠道和模板"""
    __tablename__ = "message_bindings"
    __table_args__ = {'comment': '消息绑定表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    module = Column(String(50), nullable=False, comment='所属模块')
    target_type = Column(String(50), nullable=False, comment='绑定对象类型')
    target_id = Column(Integer, nullable=True, comment='绑定对象ID')
    event_type = Column(String(50), nullable=False, comment='事件类型')
    template_id = Column(Integer, ForeignKey("message_templates.id"), nullable=True, comment='关联的模板ID')
    channel_ids = Column(JSON, default=list, comment='关联的渠道ID列表')
    config = Column(JSON, default=dict, comment="模块专用消息配置")
    is_enabled = Column(Boolean, default=True, comment='是否启用')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    template = relationship("MessageTemplate")
    creator = relationship("User")


class SchedulePolicyBinding(Base):
    """通用执行策略绑定：把时间策略挂到不同模块对象"""
    __tablename__ = "schedule_policy_bindings"
    __table_args__ = {'comment': '调度策略绑定表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    policy_id = Column(Integer, ForeignKey("api_schedule_policies.id"), nullable=False, comment='关联的策略ID')
    module = Column(String(50), nullable=False, comment='所属模块')
    target_type = Column(String(50), nullable=False, comment='绑定对象类型')
    target_id = Column(Integer, nullable=False, comment='绑定对象ID')
    task_config = Column(JSON, default=dict, comment='任务配置')
    is_enabled = Column(Boolean, default=True, comment='是否启用')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    policy = relationship("SchedulePolicy")
    creator = relationship("User")


class NavigationSystem(Base):
    """导航系统配置"""
    __tablename__ = "navigation_systems"
    __table_args__ = (
        Index("idx_navigation_systems_deleted_name", "is_deleted", "name"),
        Index("idx_navigation_systems_sort", "is_deleted", "sort_order"),
        {'comment': '导航系统表'},
    )

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='系统名称')
    sort_order = Column(Integer, default=0, comment='排序号')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    creator = relationship("User")
    apps = relationship("NavigationApp", back_populates="system")


class NavigationApp(Base):
    """统一导航应用"""
    __tablename__ = "navigation_apps"
    __table_args__ = (
        Index("idx_navigation_apps_deleted_name", "is_deleted", "app_name"),
        Index("idx_navigation_apps_created_by", "created_by"),
        Index("idx_navigation_apps_system", "system_id"),
        {'comment': '导航应用表'},
    )

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    system_id = Column(Integer, ForeignKey("navigation_systems.id"), nullable=True, comment='所属导航系统')
    app_name = Column(String(100), nullable=False, comment='应用名称')
    links = Column(JSON, default=list, comment='入口列表: [{name, url}], 最多6个')
    description = Column(Text, nullable=True, comment='备注')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    creator = relationship("User")
    system = relationship("NavigationSystem", back_populates="apps")
