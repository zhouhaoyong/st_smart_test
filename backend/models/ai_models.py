"""AI shared models — AI 模型、配额、用量记录。"""
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import JSON, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base




class AiUsageLog(Base):
    """AI 调用记录 — 用于配额统计"""
    __tablename__ = "ai_usage_logs"
    __table_args__ = {'comment': 'AI调用记录表'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True, comment="记录ID")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="操作用户ID，None=系统/cron")
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="AI调用阶段编码；展示名称按feature归类为用户功能")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="使用的模型")
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="目标类型")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="目标ID")
    tokens_estimated: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="预估Token数")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输入Token数")
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="输出Token数")
    cache_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="缓存Token数")
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="总Token数")
    provider_request_id: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="模型服务商请求标识")
    model_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="使用的AI模型ID")
    call_group_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True, comment="同一业务动作及确认重试的调用分组")
    feature: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="AI功能标识")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded", comment="调用状态：succeeded/failed/unknown")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="脱敏后的失败原因")
    quota_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否扣除平台调用额度")
    quota_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="扣除次数")
    quota_scope: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="额度范围：platform/personal/superuser")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")


class AiModel(Base):
    """AI 模型配置 — 支持多模型"""
    __tablename__ = "ai_models"
    __table_args__ = {'comment': 'AI模型配置表'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True, comment="记录ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型别名")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai-compat", comment="供应商类型")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="API 地址")
    model: Mapped[str] = mapped_column(String(100), nullable=False, comment="模型名")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密后的 API Key")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="platform", index=True, comment="模型范围：platform 平台 / personal 个人")
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="模型所有人ID")
    invalidated_reason: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="失效原因")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    show_cost: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="AI 任务后展示费用消耗")
    billing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否启用计费计算")
    billing_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="计费接口配置")
    balance_query_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否启用余额查询")
    balance_query_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="余额查询配置")
    balance_query_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="最近余额查询状态")
    balance_query_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近余额查询时间")
    connectivity_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="连通性状态：unknown/passed/failed")
    connectivity_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近连通性检测时间")
    reasoning_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="思考模式：unknown(未检测)/supported(有思考模式)/unsupported(无思考模式)")
    reasoning_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近思考模式检测时间")
    usage_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="用量统计：unknown(未检测或未等完整流)/supported(返回用量)/unsupported(明确不返回用量)")
    usage_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近用量统计检测时间")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    reasoning_profile: Mapped[str] = mapped_column(String(30), nullable=False, default="chat_template", comment="已验证的思考开启方式")
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="单次最大输出 tokens（该模型一次生成的上限，留空则用保守兜底）")


class AiPlatformQuotaSetting(Base):
    """平台模型共享日额度；所有非超管新用户自动适用。"""
    __tablename__ = "ai_platform_quota_settings"
    __table_args__ = {'comment': 'AI平台配额设置表'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, comment="平台模型共享日额度，0 表示暂停非超管平台模型使用")
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, comment="最后更新人")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class AiUserModelQuota(Base):
    """个人模型的用户自主管理日额度。"""
    __tablename__ = "ai_user_model_quotas"
    __table_args__ = (
        UniqueConstraint("user_id", "model_id", name="uq_ai_user_model_quota"),
        {'comment': '用户模型配额表'},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="模型所有人ID")
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_models.id"), nullable=False, index=True, comment="个人模型ID")
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, comment="个人模型每日调用额度，配额记录必须为正整数")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class AiModelDetectionLog(Base):
    """模型能力检测历史；检测不计入平台 AI 额度。"""
    __tablename__ = "ai_model_detection_logs"
    __table_args__ = {'comment': 'AI模型能力检测日志表'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_models.id"), nullable=False, index=True, comment="被检测模型ID")
    operator_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="检测操作人ID")
    connectivity_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="连通性检测状态")
    reasoning_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="思考能力检测状态")
    usage_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", comment="用量返回能力检测状态：unknown(未检测或未等完整流)/supported(返回用量)/unsupported(明确不返回用量)")
    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="脱敏后的检测结果")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除标记")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="删除时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="检测时间")
