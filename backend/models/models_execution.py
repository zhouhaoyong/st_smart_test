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


class ExecutionSet(Base):
    """执行集模型"""
    __tablename__ = "api_execution_sets"
    __table_args__ = {'comment': '执行集表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='执行集名称')
    description = Column(Text, nullable=True, comment='执行集描述')
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    environment_id = Column(Integer, ForeignKey("api_environments.id"), comment='关联的环境ID')  # 运行环境
    parameter_set_id = Column(Integer, ForeignKey("api_parameter_sets.id"), nullable=True, comment='关联参数集')
    schedule_policy_id = Column(Integer, ForeignKey("api_schedule_policies.id"), nullable=True, comment='关联执行策略')
    retry_count = Column(Integer, default=0, comment='失败重试次数')  # 失败重试次数
    cron_expression = Column(String(100), comment='定时执行表达式')  # 定时执行表达式
    is_enabled = Column(Boolean, default=True, comment='是否启用定时执行')  # 是否启用定时执行
    last_scheduled_run_at = Column(DateTime(timezone=True), nullable=True, comment='上次定时触发时间')
    next_scheduled_run_at = Column(DateTime(timezone=True), nullable=True, comment='下次定时触发时间')
    scheduler_status = Column(String(20), default="idle", comment='调度状态: idle/running/disabled/error')
    scheduler_started_at = Column(DateTime(timezone=True), nullable=True, comment='当前调度开始时间')
    scheduler_error = Column(Text, nullable=True, comment='最近调度错误')
    notification_config = Column(JSON, default=dict, comment='通知配置')  # 通知配置
    execution_mode = Column(String(20), default="serial", comment='执行方式: serial/parallel')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="execution_sets")
    environment = relationship("Environment")
    parameter_set = relationship("ParameterSet")
    schedule_policy = relationship("SchedulePolicy", back_populates="execution_sets")
    execution_items = relationship("ExecutionItem", back_populates="execution_set")


class SchedulePolicy(Base):
    """执行策略模型"""
    __tablename__ = "api_schedule_policies"
    __table_args__ = {'comment': '调度策略表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, unique=True, comment='策略名称')
    description = Column(Text, nullable=True, comment='策略描述')
    schedule_type = Column(String(30), nullable=False, default="daily_times", comment='调度类型：daily_times/weekly_times/interval/cron')
    schedule_config = Column(JSON, default=dict, comment='人性化调度配置')
    cron_expression = Column(String(255), nullable=True, comment='兼容/高级 Cron 表达式')
    max_references = Column(Integer, nullable=True, comment='最大引用次数，空则使用系统默认值')
    is_enabled = Column(Boolean, default=True, comment='是否启用')
    last_triggered_at = Column(DateTime(timezone=True), nullable=True, comment='上次触发时间')
    next_trigger_at = Column(DateTime(timezone=True), nullable=True, comment='下次触发时间')
    last_status = Column(String(20), nullable=True, comment='最近调度状态')
    last_summary = Column(JSON, default=dict, comment='最近调度摘要')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    creator = relationship("User")
    execution_sets = relationship("ExecutionSet", back_populates="schedule_policy")


class ScheduleRunLog(Base):
    """执行策略调度日志"""
    __tablename__ = "api_schedule_run_logs"
    __table_args__ = {'comment': '调度运行日志表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    policy_id = Column(Integer, ForeignKey("api_schedule_policies.id"), nullable=False, comment='关联的策略ID')
    execution_set_id = Column(Integer, ForeignKey("api_execution_sets.id"), nullable=True, comment='关联的执行集ID')
    report_id = Column(Integer, ForeignKey("api_reports.id"), nullable=True, comment='关联的报告ID')
    status = Column(String(20), default="pending", comment='调度运行状态：triggered/running/success/failed/skipped')
    message_status = Column(String(20), nullable=True, comment='消息发送状态：success/failed/skipped')
    message_detail = Column(Text, nullable=True, comment='消息发送详情')
    detail = Column(Text, nullable=True, comment='日志详情')
    triggered_at = Column(DateTime(timezone=True), default=beijing_now, comment='触发时间')
    finished_at = Column(DateTime(timezone=True), nullable=True, comment='完成时间')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')

    policy = relationship("SchedulePolicy")
    execution_set = relationship("ExecutionSet")
    report = relationship("Report")


class ExecutionItem(Base):
    """执行项模型（执行集中的用例）"""
    __tablename__ = "api_execution_items"
    __table_args__ = {'comment': '执行集项表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    execution_set_id = Column(Integer, ForeignKey("api_execution_sets.id"), comment='关联的执行集ID')
    test_case_id = Column(Integer, ForeignKey("api_test_cases.id"), comment='关联的用例ID')
    order = Column(Integer, nullable=False, comment='执行顺序')  # 执行顺序
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')

    # 关系
    execution_set = relationship("ExecutionSet", back_populates="execution_items")
    test_case = relationship("TestCase")


class Report(Base):
    """测试报告模型"""
    __tablename__ = "api_reports"
    __table_args__ = {'comment': '测试报告表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='报告名称')  # 执行集名+时间戳
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    execution_set_id = Column(Integer, ForeignKey("api_execution_sets.id"), comment='关联的执行集ID')
    status = Column(String(20), default="running", comment='报告状态: running/success/failed')  # running, success, failed
    start_time = Column(DateTime(timezone=True), nullable=True, comment='开始时间')
    end_time = Column(DateTime(timezone=True), nullable=True, comment='结束时间')
    duration = Column(Integer, nullable=True, comment='耗时(毫秒)')  # 耗时（毫秒）
    total_steps = Column(Integer, default=0, comment='总步骤数')
    passed_steps = Column(Integer, default=0, comment='通过步骤数')
    failed_steps = Column(Integer, default=0, comment='失败步骤数')
    total_cases = Column(Integer, default=0, comment='总用例数')
    passed_cases = Column(Integer, default=0, comment='通过用例数')
    failed_cases = Column(Integer, default=0, comment='失败用例数')
    pass_rate = Column(Float, default=0.0, comment='用例通过率')  # 通过率（用例维度）
    execution_mode = Column(String(20), default="serial", comment='执行方式快照: serial/parallel')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')

    # 关系
    project = relationship("Project", back_populates="reports")
    execution_set = relationship("ExecutionSet")
    report_details = relationship("ReportDetail", back_populates="report")


class ReportDetail(Base):
    """报告详情模型"""
    __tablename__ = "api_report_details"
    __table_args__ = {'comment': '测试报告明细表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    report_id = Column(Integer, ForeignKey("api_reports.id"), comment='关联的报告ID')
    step_order = Column(Integer, nullable=False, comment='步骤顺序')  # 步骤顺序
    test_case_id = Column(Integer, ForeignKey("api_test_cases.id"), nullable=True, comment='所属用例')
    status = Column(String(20), nullable=True, comment='步骤状态: success/failed')  # success, failed
    request_data = Column(JSON, nullable=True, comment='请求数据')  # 请求数据
    response_data = Column(JSON, nullable=True, comment='响应数据')  # 响应数据
    expected_response = Column(JSON, nullable=True, comment='预期响应')  # 预期响应
    actual_response = Column(JSON, nullable=True, comment='实际响应')  # 实际响应
    diff_result = Column(JSON, nullable=True, comment='差异对比结果')  # 差异对比结果
    logs = Column(Text, nullable=True, comment='脚本日志')  # 脚本日志
    duration = Column(Integer, nullable=True, comment='步骤耗时(毫秒)')  # 步骤耗时（毫秒）
    retry_attempts = Column(Integer, default=0, comment='重试次数')
    error_message = Column(Text, nullable=True, comment='错误信息')  # 错误信息
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')

    # 关系
    report = relationship("Report", back_populates="report_details")
    test_case = relationship("TestCase")


class ReportSendLog(Base):
    """报告发送日志"""
    __tablename__ = "api_report_send_logs"
    __table_args__ = {'comment': '报告发送日志表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    report_id = Column(Integer, ForeignKey("api_reports.id"), nullable=False, comment='关联的报告ID')
    channel_id = Column(Integer, ForeignKey("message_channels.id"), nullable=True, comment='关联的渠道ID')
    channel_name = Column(String(50), nullable=True, comment='发送渠道名称')
    status = Column(String(20), default='pending', comment='发送状态: pending/success/failed')
    message_detail = Column(Text, nullable=True, comment='发送详情或错误信息')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    sent_at = Column(DateTime(timezone=True), default=beijing_now, comment='发送时间')

    report = relationship("Report")
