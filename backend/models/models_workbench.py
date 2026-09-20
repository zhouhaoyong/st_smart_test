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


class TWProject(Base):
    """测试工作台项目表"""
    __tablename__ = "tw_projects"
    __table_args__ = {'comment': '测试工作台项目表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='项目名称')
    description = Column(Text, nullable=True, comment='项目描述')
    tags = Column(JSON, default=list, comment='标签列表')
    color = Column(String(20), nullable=True, comment='主题色')
    is_public = Column(Boolean, default=True, comment='是否公开')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')
class TWSystem(Base):
    """测试工作台系统 / 端表"""
    __tablename__ = "tw_systems"
    __table_args__ = {'comment': '测试工作台系统 / 端表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    name = Column(String(100), nullable=False, comment='系统或端名称')
    type = Column(String(50), nullable=True, comment='系统类型或端类型')
    description = Column(Text, nullable=True, comment='系统说明')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWVersion(Base):
    """测试工作台系统版本表"""
    __tablename__ = "tw_versions"
    __table_args__ = {'comment': '测试工作台系统版本表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_no = Column(String(100), nullable=False, comment='版本号')
    description = Column(Text, nullable=True, comment='版本说明')
    plan_release_date = Column(String(50), nullable=True, comment='计划发布日期（纯文案记录，不做日期校验/联动）')
    actual_release_date = Column(String(50), nullable=True, comment='实际发布日期（纯文案记录，不做日期校验/联动）')
    current_stage = Column(String(100), nullable=True, comment='当前阶段（纯文案记录，如：需求评审/开发中/测试中/已发布）')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWRequirement(Base):
    """测试工作台原始需求表"""
    __tablename__ = "tw_requirements"
    __table_args__ = {'comment': '测试工作台原始需求表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='系统版本ID')
    title = Column(String(200), nullable=False, comment='需求标题')
    source_type = Column(String(50), default='manual', comment='来源类型')
    original_content = Column(MEDIUMTEXT, nullable=True, comment='原始需求内容（用户初始输入）')
    markdown_content = Column(MEDIUMTEXT, nullable=True, comment='需求正文（Markdown，与结构化解耦，确认与后续流程主依据）')
    req_no = Column(String(40), nullable=True, index=True, comment='原始需求唯一编号（保存时分配，稳定不变）')
    confirm_status = Column(String(30), default='draft', comment='确认状态（两态）：draft 待确认 / confirmed 已确认')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWCompletedRequirement(Base):
    """测试工作台补全需求表：AI 补全结果独立保存，始终追溯到原始需求。"""
    __tablename__ = "tw_completed_requirements"
    __table_args__ = {'comment': '测试工作台补全需求表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    source_requirement_id = Column(Integer, ForeignKey("tw_requirements.id"), nullable=False, index=True, comment='来源原始需求ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='系统版本ID')
    title = Column(String(200), nullable=False, comment='补全需求标题')
    markdown_content = Column(MEDIUMTEXT, nullable=False, comment='补全后的 Markdown 正文')
    req_no = Column(String(40), nullable=True, index=True, comment='AI补全需求唯一编号（保存时分配，稳定不变）')
    confirm_status = Column(String(30), default='draft', comment='确认状态（两态）：draft 待确认 / confirmed 已确认')
    is_stale = Column(Boolean, default=False, comment='来源原始需求更新后是否可能过期')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWMergedRequirement(Base):
    """测试工作台合并需求表（单系统单版本内多条已确认需求合并而成的派生实体）。

    结构化需求（固定 5 键）仅挂在合并需求上、AI 按需生成、与正文解耦（单独 JSON 列，可为空）。
    """
    __tablename__ = "tw_merged_requirements"
    __table_args__ = {'comment': '测试工作台合并需求表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='系统版本ID')
    title = Column(String(200), nullable=False, comment='合并需求标题')
    req_no = Column(String(40), nullable=True, index=True, comment='AI合并需求唯一编号（保存时分配，稳定不变）')
    markdown_content = Column(MEDIUMTEXT, nullable=True, comment='合并后的 Markdown 正文（人工确认后保存）')
    structure_json = Column(JSON, default=dict, comment='结构化需求JSON（固定5键，AI按需生成，只读，可为空，与正文解耦）')
    source_requirement_ids = Column(JSON, default=list, comment='来源需求快照：[{source_type, source_id, title, req_no, version_pointer}]')
    is_stale = Column(Boolean, default=False, comment='是否可能过期（来源需求在合并后被编辑）')
    confirm_status = Column(String(30), default='draft', comment='确认状态（两态）：draft 待确认 / confirmed 已确认')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWTestCase(Base):
    """测试工作台测试用例表"""
    __tablename__ = "tw_test_cases"
    __table_args__ = {'comment': '测试工作台测试用例表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='系统版本ID')
    requirement_id = Column(Integer, ForeignKey("tw_requirements.id"), nullable=True, comment='关联需求ID（弱关联）')
    completed_requirement_id = Column(Integer, ForeignKey("tw_completed_requirements.id"), nullable=True, comment='关联补全需求ID（弱关联）')
    merged_requirement_id = Column(Integer, ForeignKey("tw_merged_requirements.id"), nullable=True, comment='关联合并需求ID（弱关联）')
    case_no = Column(String(100), nullable=True, comment='用例编号')
    title = Column(String(200), nullable=False, comment='用例标题')
    scenario = Column(Text, nullable=True, comment='覆盖场景')
    case_type = Column(String(50), nullable=True, comment='用例类型')
    precondition = Column(Text, nullable=True, comment='前置条件')
    test_data = Column(JSON, default=dict, comment='测试数据')
    steps_json = Column(JSON, default=list, comment='测试步骤JSON')
    expected_result = Column(Text, nullable=True, comment='预期结果')
    priority = Column(String(30), default='P2', comment='优先级')
    confirm_status = Column(String(30), default='draft', comment='确认状态（两态）：draft 待确认 / confirmed 已确认')
    execution_status = Column(String(30), default='not_executed', comment='执行状态')
    source_type = Column(String(50), default='manual', comment='来源类型')
    source_ref = Column(String(255), nullable=True, comment='来源引用')
    tags = Column(JSON, default=list, comment='标签')
    business_flow_refs = Column(JSON, default=list, comment='关联业务流程引用')
    function_point_refs = Column(JSON, default=list, comment='关联功能点引用')
    requirement_structure_refs = Column(JSON, default=list, comment='关联结构化需求引用')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWTestExecution(Base):
    """测试工作台测试执行结果表"""
    __tablename__ = "tw_test_executions"
    __table_args__ = {'comment': '测试工作台测试执行结果表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    test_case_id = Column(Integer, ForeignKey("tw_test_cases.id"), nullable=False, comment='测试用例ID')
    result = Column(String(30), nullable=False, comment='执行结果')
    actual_result = Column(Text, nullable=True, comment='实际结果')
    remark = Column(Text, nullable=True, comment='执行备注')
    not_tested_reason = Column(Text, nullable=True, comment='未测原因')
    blocked_reason = Column(Text, nullable=True, comment='阻塞原因')
    executed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='执行人ID')
    executed_at = Column(DateTime(timezone=True), default=beijing_now, comment='执行时间')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWBugRecord(Base):
    """测试工作台 Bug 记录表"""
    __tablename__ = "tw_bug_records"
    __table_args__ = {'comment': '测试工作台 Bug 记录表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='系统版本ID')
    requirement_id = Column(Integer, ForeignKey("tw_requirements.id"), nullable=True, comment='关联需求ID（弱关联）')
    merged_requirement_id = Column(Integer, ForeignKey("tw_merged_requirements.id"), nullable=True, comment='关联合并需求ID（弱关联）')
    test_case_id = Column(Integer, ForeignKey("tw_test_cases.id"), nullable=True, comment='关联测试用例ID')
    execution_id = Column(Integer, ForeignKey("tw_test_executions.id"), nullable=True, comment='关联执行结果ID')
    title = Column(String(200), nullable=False, comment='Bug 标题')
    steps = Column(Text, nullable=True, comment='复现步骤')
    actual_result = Column(Text, nullable=True, comment='实际结果')
    expected_result = Column(Text, nullable=True, comment='预期结果')
    severity = Column(String(30), default='major', comment='严重程度')
    priority = Column(String(30), default='P2', comment='优先级')
    status = Column(String(30), default='pending', comment='处理状态：pending 待解决 / resolved 已解决 / closed 已验证关闭')
    verify_result = Column(String(30), nullable=True, comment='验证结果：pass / fail')
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment='指派处理人ID')
    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment='验证人ID（默认 Bug 发起人）')
    resolution = Column(Text, nullable=True, comment='解决方案说明')
    verify_conclusion = Column(Text, nullable=True, comment='验证结论')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')


class TWBugTransition(Base):
    """测试工作台 Bug 流转记录表：留痕每次状态变更。"""
    __tablename__ = "tw_bug_transitions"
    __table_args__ = {'comment': '测试工作台 Bug 流转记录表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    bug_id = Column(Integer, ForeignKey("tw_bug_records.id"), nullable=False, index=True, comment='关联缺陷记录ID')
    action = Column(String(30), nullable=False, comment='流转动作：submit/assign/resolve/verify/reactivate')
    from_status = Column(String(30), nullable=True, comment='原状态')
    to_status = Column(String(30), nullable=True, comment='新状态')
    remark = Column(Text, nullable=True, comment='流转说明')
    operated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='操作人ID')
    operated_at = Column(DateTime(timezone=True), default=beijing_now, comment='操作时间')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')


class TWLegacyItem(Base):
    """测试工作台遗留项表"""
    __tablename__ = "tw_legacy_items"
    __table_args__ = {'comment': '测试工作台遗留项表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    project_id = Column(Integer, ForeignKey("tw_projects.id"), nullable=False, comment='工作台项目ID')
    system_id = Column(Integer, ForeignKey("tw_systems.id"), nullable=False, comment='系统 / 端ID')
    version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=False, comment='当前版本ID')
    planned_version_id = Column(Integer, ForeignKey("tw_versions.id"), nullable=True, comment='计划处理版本ID')
    requirement_id = Column(Integer, ForeignKey("tw_requirements.id"), nullable=True, comment='关联需求ID（弱关联）')
    merged_requirement_id = Column(Integer, ForeignKey("tw_merged_requirements.id"), nullable=True, comment='关联合并需求ID（弱关联）')
    test_case_id = Column(Integer, ForeignKey("tw_test_cases.id"), nullable=True, comment='关联测试用例ID')
    bug_id = Column(Integer, ForeignKey("tw_bug_records.id"), nullable=True, comment='关联 Bug ID')
    title = Column(String(200), nullable=False, comment='遗留项标题')
    type = Column(String(50), default='bug', comment='遗留项类型')
    description = Column(Text, nullable=True, comment='遗留项描述')
    source_type = Column(String(50), nullable=True, comment='来源类型')
    priority = Column(String(30), default='P2', comment='优先级')
    status = Column(String(30), default='pending', comment='状态')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')
    creator = relationship("User", foreign_keys=[created_by])
