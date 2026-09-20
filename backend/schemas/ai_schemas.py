"""AI schemas — Pydantic models for AI model/quota request/response."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AiModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = "openai-compat"
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=100)
    api_key: str | None = None
    scope: str | None = None
    enabled: bool = True
    show_cost: bool = False
    billing_enabled: bool = False
    billing_config: dict | None = None
    balance_query_enabled: bool = False
    balance_query_config: dict | None = None
    max_output_tokens: int | None = None
    connectivity_verified: bool = False
    # 新建时若已在弹窗内完成模型能力检测，随保存一并落库；检测结果仅作配置参考。
    reasoning_status: str | None = None
    reasoning_profile: str | None = None
    usage_status: str | None = None


class AiModelUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    scope: str | None = None
    enabled: bool | None = None
    show_cost: bool | None = None
    billing_enabled: bool | None = None
    billing_config: dict | None = None
    balance_query_enabled: bool | None = None
    balance_query_config: dict | None = None
    max_output_tokens: int | None = None
    connectivity_verified: bool | None = None
    # 编辑时若连接配置有变更并在弹窗内重新完成了「模型能力检测」，把检测结果随保存一并落库，
    # 避免 connection_changed 分支把刚测到的思考 / 用量能力重置为未检测。
    reasoning_status: str | None = None
    reasoning_profile: str | None = None
    usage_status: str | None = None


class AiModelConnectivityRequest(BaseModel):
    provider: str = "openai-compat"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    model_id: int | None = None
    scope: str = "platform"


class AiModelBillingTestRequest(BaseModel):
    provider: str = "openai-compat"
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    balance_query_config: dict | None = None


class AiModelRead(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str | None = None
    model: str
    has_api_key: bool = False
    api_key_masked: str | None = None
    scope: str = "platform"
    owner_user_id: int | None = None
    enabled: bool
    show_cost: bool = False
    billing_enabled: bool = False
    balance_query_enabled: bool | None = None
    balance_query_configured: bool | None = None
    balance_query_status: str | None = None
    balance_query_checked_at: datetime | None = None
    can_edit: bool = False
    can_test: bool = False
    can_query_balance: bool = False
    max_output_tokens: int | None = None
    connectivity_status: str = "unknown"
    connectivity_checked_at: datetime | None = None
    reasoning_status: str = "unknown"
    reasoning_checked_at: datetime | None = None
    usage_status: str = "unknown"
    usage_checked_at: datetime | None = None
    created_by: int | None = None
    creator_name: str | None = None
    created_at: datetime
    updated_at: datetime
    balance: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AiModelFetchRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model_id: int | None = None


class AiModelQuotaRequest(BaseModel):
    daily_limit: int = Field(gt=0)


class AiPlatformQuotaSettingRequest(BaseModel):
    daily_limit: int = Field(gt=0)
