from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def _ensure_optional_title_not_blank(value: Any) -> Any:
    """编辑类 schema 的可选 title：为 None 表示不改，跳过；提供了但去空白后为空则报错。"""
    if value is not None and not str(value).strip():
        raise ValueError("标题不能为空")
    return value


def _normalize_test_case_steps(value: Any) -> list[dict[str, Any]] | None:
    """兼容 AI 返回的字符串步骤，并统一为可持久化的对象数组。"""
    if value is None:
        return None
    if not isinstance(value, list):
        return []
    steps: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                steps.append({"step": text})
        elif isinstance(item, dict):
            steps.append(item)
    return steps


def _normalize_test_data(value: Any) -> dict[str, Any]:
    """兼容 AI 把测试数据返成数组/字符串/空值等非对象的情况，统一归一为对象。
    否则用户未进预览编辑直接保存时，单条格式不符会导致整批保存被拒且报错不指明字段。"""
    if not isinstance(value, dict):
        return {}
    return value


def _normalize_optional_test_data(value: Any) -> dict[str, Any] | None:
    """编辑类 schema 的可选测试数据：None 表示不修改，保留；其余非对象归一为对象。"""
    if value is None:
        return None
    return _normalize_test_data(value)


class TWProjectCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    color: str | None = None
    is_public: bool = True


class TWProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    color: str | None = None
    is_public: bool | None = None


class TWProjectBusinessCleanup(BaseModel):
    system_ids: list[int] = Field(min_length=1)
    asset_types: list[Literal["system", "version", "requirement", "test_case", "bug", "legacy_item"]] = Field(min_length=1)

    @field_validator("system_ids")
    @classmethod
    def _validate_system_ids(cls, value: list[int]) -> list[int]:
        result = list(dict.fromkeys(item for item in value if item > 0))
        if not result:
            raise ValueError("请至少选择一个系统")
        return result

    @field_validator("asset_types")
    @classmethod
    def _validate_asset_types(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class TWSystemCreate(BaseModel):
    project_id: int
    name: str
    type: str | None = None
    description: str | None = None


class TWSystemUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    description: str | None = None


class TWVersionCreate(BaseModel):
    project_id: int
    system_id: int
    version_no: str
    description: str | None = None
    plan_release_date: str | None = None
    actual_release_date: str | None = None
    current_stage: str = Field(min_length=1)
    confirm_lower_version: bool = False


class TWVersionUpdate(BaseModel):
    version_no: str | None = None
    description: str | None = None
    plan_release_date: str | None = None
    actual_release_date: str | None = None
    # 编辑版本时可只改日期而不重传阶段，故放宽为可选。
    current_stage: str | None = None
    confirm_lower_version: bool = False


class TWRequirementSave(BaseModel):
    """单条需求：仅原始输入 + AI 撰写的 Markdown 正文，不含结构化（结构只挂在合并需求上）。"""
    project_id: int
    system_id: int
    version_id: int
    title: str = Field(min_length=1)
    original_content: str = ""
    markdown_content: str | None = None
    source_type: str = "manual"


class TWRequirementUpdate(BaseModel):
    title: str | None = None
    original_content: str | None = None
    markdown_content: str | None = None

    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)


class TWRequirementBatchDelete(BaseModel):
    """批量删除需求：按 id 列表删除；或在指定系统版本作用域下「全部删除」。"""
    ids: list[int] = Field(default_factory=list)
    project_id: int | None = None
    system_ids: list[int] = Field(default_factory=list)
    version_id: int | None = None
    version_ids: list[int] = Field(default_factory=list)
    delete_all_in_scope: bool = False
    title: str | None = None
    status: str | None = None
    created_from: str | None = None
    created_to: str | None = None


class TWRequirementBatchConfirm(BaseModel):
    """批量确认当前作用域内选中的需求类记录。"""
    ids: list[int] = Field(min_length=1)
    project_id: int | None = None
    system_ids: list[int] = Field(default_factory=list)
    version_id: int | None = None
    version_ids: list[int] = Field(default_factory=list)


class TWRequirementHistoryItem(BaseModel):
    """一条追问问答。AI 补全的会话状态**由前端持有**并每次随请求回传，后端不落库。

    - status='answered' 时 answer 为用户回答文本（选项与自定义输入已由前端合并成一句）；
    - status='skipped' 表示用户明确跳过，后端据此保证「永不重问」；
    - status='pending' 表示曾展示但用户未处理，需继续挂在界面上。
    - id 由后端首次生成，后续轮次原样回传，用于稳定绑定问题与回答。
    """
    id: str | None = Field(default=None, max_length=100)
    text: str = Field(min_length=1)
    category: str = "must_confirm"
    type: str = "open"
    options: list[str] = Field(default_factory=list)
    recommended: str = ""
    multi: bool = False
    status: Literal["answered", "skipped", "pending"] = "pending"
    answer: str = ""
    selected_options: list[str] = Field(default_factory=list)
    custom_answer: str = ""
    action: Literal["answer", "skip"] = "answer"


class TWRequirementAiAsk(BaseModel):
    """一轮追问请求。无状态：全部上下文随请求携带，需求原文由后端从库里读。"""
    # 已提交的回答轮次（0 = 首轮）。后端会做区间收敛，不信任其准确性。
    round: int = 0
    # 累积问答历史（含本轮刚提交的），是唯一的会话状态。
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    # 本轮新处理的问答子集，仅用于装配「用户最新回复」，也已包含在 history 中。
    answers: list[TWRequirementHistoryItem] = Field(default_factory=list)
    # 不对应具体问题的用户补充；前端仅展示本轮消息，但每次请求都会携带累计内容以保持上下文连续。
    supplements: list[str] = Field(default_factory=list)
    supplement: str = ""
    # 仅首轮可选：用户在补全入口修改过的原始需求正文，会先落库再开始追问。
    initial_content: str | None = None
    # 本次操作临时指定模型；不改变模型配置。
    selected_model_id: int | None = Field(default=None, gt=0)
    # 用户确认重试时沿用，关联同一次业务操作下的多次真实调用。
    call_group_id: str | None = Field(default=None, max_length=100)


class TWRequirementAiCompose(BaseModel):
    """结束对话并补全需求：基于问答历史在原文上修订出新正文，不落库。"""
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    selected_model_id: int | None = Field(default=None, gt=0)
    call_group_id: str | None = Field(default=None, max_length=100)


class TWRequirementAiCompare(BaseModel):
    """核对本次 AI 整理结果是否纳入用户确认内容，仅返回审查结论。"""
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    markdown_content: str = Field(min_length=1)
    selected_model_id: int | None = Field(default=None, gt=0)
    call_group_id: str | None = Field(default=None, max_length=100)


class TWRequirementAiSave(BaseModel):
    """AI 补全预览保存：创建独立补全需求，默认待确认。"""
    markdown_content: str = Field(min_length=1)


class TWCompletedRequirementSave(BaseModel):
    """补全需求编辑或保存时允许修改标题和正文，不影响原始需求。"""
    title: str | None = None
    markdown_content: str = Field(min_length=1)

    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)


class TWMergeAiScope(BaseModel):
    """对话式 AI 合并的作用域：同一次仅能使用一种已确认来源。

    合并对话在保存前没有任何业务记录，会话状态又不落库，因此作用域必须**每次请求都携带**，
    后端据此重新从库里读取来源需求正文（不缓存、不截断），保证模型每轮都看到完整来源。
    """
    version_id: int
    source_type: Literal["requirement", "completed_requirement"]
    source_ids: list[int] = Field(min_length=1)
    title: str | None = None
    selected_model_id: int | None = Field(default=None, gt=0)
    call_group_id: str | None = Field(default=None, max_length=100)


class TWMergeAiAsk(TWMergeAiScope):
    """对话式 AI 合并的一轮追问（无状态，同 TWRequirementAiAsk 语义）。"""
    round: int = 0
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    answers: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    supplement: str = ""


class TWMergeAiCompose(TWMergeAiScope):
    """对话式 AI 合并的整理成文（无状态，仅返回未保存的预览内容）。"""
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class TWMergeAiCompare(TWMergeAiScope):
    """对话式 AI 合并结果的只读核对。"""
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    markdown_content: str = Field(min_length=1)


class TWMergeAiSave(TWMergeAiScope):
    """对话式 AI 合并保存：创建已落库、待确认的 AI 合并需求。"""
    markdown_content: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def _validate_merge_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            raise ValueError("需求标题不能为空")
        if len(title) > 20:
            raise ValueError("需求标题不能超过20个字")
        return title


class TWMergedRequirementRemergeSave(BaseModel):
    """重新合并保存：更新正文、刷新来源列表并清除过期标记。"""
    title: str = Field(min_length=1)
    markdown_content: str = ""
    source_ids: list[int] = Field(min_length=1)


class TWMergedRequirementUpdate(BaseModel):
    title: str | None = None
    markdown_content: str | None = None

    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)


class TWTestCaseCreate(BaseModel):
    project_id: int
    system_id: int
    version_id: int
    requirement_id: int | None = None
    completed_requirement_id: int | None = None
    merged_requirement_id: int | None = None
    title: str = Field(min_length=1)
    scenario: str | None = None
    case_type: str | None = None
    precondition: str | None = None
    test_data: dict[str, Any] = Field(default_factory=dict)
    steps_json: list[dict[str, Any]] = Field(default_factory=list)
    expected_result: str | None = None
    priority: str = "P2"
    execution_status: str = "not_executed"
    source_type: str = "manual"
    source_ref: str | None = None
    tags: list[str] = Field(default_factory=list)
    business_flow_refs: list[Any] = Field(default_factory=list)
    function_point_refs: list[Any] = Field(default_factory=list)
    requirement_structure_refs: list[Any] = Field(default_factory=list)

    _normalize_steps_json = field_validator("steps_json", mode="before")(_normalize_test_case_steps)
    _normalize_test_data = field_validator("test_data", mode="before")(_normalize_test_data)


class TWTestCaseUpdate(BaseModel):
    requirement_id: int | None = None
    completed_requirement_id: int | None = None
    merged_requirement_id: int | None = None
    title: str | None = None
    scenario: str | None = None
    case_type: str | None = None
    precondition: str | None = None
    test_data: dict[str, Any] | None = None
    steps_json: list[dict[str, Any]] | None = None
    expected_result: str | None = None
    priority: str | None = None
    tags: list[str] | None = None

    _normalize_steps_json = field_validator("steps_json", mode="before")(_normalize_test_case_steps)
    _normalize_test_data = field_validator("test_data", mode="before")(_normalize_optional_test_data)
    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)


class TWTestCaseBatchOperate(BaseModel):
    ids: list[int] = Field(default_factory=list)
    project_id: int | None = None
    system_ids: list[int] = Field(default_factory=list)
    version_id: int | None = None
    version_ids: list[int] = Field(default_factory=list)
    delete_all_in_scope: bool = False
    confirm_all_in_scope: bool = False
    confirm_status: str | None = None
    case_no: str | None = None
    title: str | None = None
    source: str | None = None
    priority: str | None = None
    case_type: str | None = None
    status: str | None = None
    created_from: str | None = None
    created_to: str | None = None


class TWTestCaseBatchExecute(BaseModel):
    """为当前列表中选中的已确认用例统一追加一条执行记录。"""
    ids: list[int] = Field(min_length=1)
    project_id: int
    system_ids: list[int] = Field(default_factory=list)
    version_id: int | None = None
    version_ids: list[int] = Field(default_factory=list)
    result: Literal["passed", "failed", "not_executed"]


class TWTestCaseBatchCreate(BaseModel):
    cases: list[TWTestCaseCreate] = Field(min_length=1)


class TWTestCaseGenerateScope(BaseModel):
    """用例生成来源：当前项目筛选范围内的一种已确认需求类型。"""
    project_id: int
    source_type: Literal["requirement", "completed_requirement", "merged_requirement"]
    source_ids: list[int] = Field(min_length=1)
    system_ids: list[int] = Field(default_factory=list)
    version_ids: list[int] = Field(default_factory=list)
    selected_model_id: int | None = Field(default=None, gt=0)
    call_group_id: str | None = Field(default=None, max_length=100)


class TWTestCasePreflightAsk(TWTestCaseGenerateScope):
    """用例生成前的首轮必要追问；会话状态仅由前端回传。"""
    round: int = 0
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    answers: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    supplement: str = ""


class TWTestCaseGenerateRequest(TWTestCaseGenerateScope):
    """基于已确认需求和预检结论直接生成测试用例预览。"""
    history: list[TWRequirementHistoryItem] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    preflight_completed: bool = False


class TWTestExecutionCreate(BaseModel):
    test_case_id: int
    result: Literal["passed", "failed", "not_executed"]
    actual_result: str | None = None
    remark: str | None = None


class TWTestExecutionUpdate(BaseModel):
    """更正最近一次执行记录（历史其它记录保留）。"""
    result: Literal["passed", "failed", "not_executed"]
    actual_result: str | None = None
    remark: str | None = None


class TWBugCreate(BaseModel):
    project_id: int
    system_id: int
    version_id: int
    requirement_id: int | None = None
    merged_requirement_id: int | None = None
    test_case_id: int | None = None
    execution_id: int | None = None
    title: str = Field(min_length=1)
    steps: str | None = None
    actual_result: str | None = None
    expected_result: str | None = None
    severity: str = "major"
    priority: str = "P2"
    status: str = "pending"
    verify_result: str | None = None
    assignee_id: int | None = None
    resolution: str | None = None
    verify_conclusion: str | None = None


class TWBugUpdate(BaseModel):
    requirement_id: int | None = None
    merged_requirement_id: int | None = None
    test_case_id: int | None = None
    execution_id: int | None = None
    title: str | None = None
    steps: str | None = None
    actual_result: str | None = None
    expected_result: str | None = None
    severity: str | None = None
    priority: str | None = None
    assignee_id: int | None = None
    verifier_id: int | None = None

    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)


class TWBugBatchOperate(BaseModel):
    """批量删除 Bug：仅允许删除当前项目作用域内选中的记录。"""
    ids: list[int] = Field(min_length=1)
    project_id: int
    system_ids: list[int] = Field(default_factory=list)
    version_id: int | None = None
    version_ids: list[int] = Field(default_factory=list)


class TWBugAssign(BaseModel):
    """指派处理人。"""
    assignee_id: int | None = None
    remark: str | None = None


class TWBugResolve(BaseModel):
    """开发标记已解决。"""
    resolution: str = Field(min_length=1)


class TWBugVerify(BaseModel):
    """测试验证：pass 关闭 / fail 重新激活。"""
    result: str = Field(pattern="^(pass|fail)$")
    verify_conclusion: str | None = None

    @field_validator("verify_conclusion")
    @classmethod
    def _require_reason_when_fail(cls, value: str | None, info) -> str | None:
        # 验证不通过（fail，重新激活）必须填写原因，pass 分支可选。
        if info.data.get("result") == "fail" and not str(value or "").strip():
            raise ValueError("请填写重新激活原因")
        return value


class TWLegacyCreate(BaseModel):
    project_id: int
    system_id: int
    version_id: int
    planned_version_id: int | None = None
    requirement_id: int | None = None
    merged_requirement_id: int | None = None
    test_case_id: int | None = None
    bug_id: int | None = None
    title: str = Field(min_length=1)
    type: str = "bug"
    description: str | None = None
    source_type: str | None = None
    priority: str = "P2"
    status: str = "pending"


class TWLegacyUpdate(BaseModel):
    planned_version_id: int | None = None
    requirement_id: int | None = None
    merged_requirement_id: int | None = None
    test_case_id: int | None = None
    bug_id: int | None = None
    title: str | None = None
    type: str | None = None
    description: str | None = None
    source_type: str | None = None
    priority: str | None = None
    status: str | None = None

    _validate_title = field_validator("title")(_ensure_optional_title_not_blank)
