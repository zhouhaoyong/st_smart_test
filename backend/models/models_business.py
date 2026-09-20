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


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    __table_args__ = (
        Index('inx_id', 'id'),
        Index('inx_phone', 'phone'),
        {'comment': '用户表'}
    )

    # 必填字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='id')
    phone: Mapped[str] = mapped_column(String(11), unique=True, nullable=False, comment='手机号')
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment='密码')
    real_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment='真实姓名')
    nick_name: Mapped[str] = mapped_column(String(50), nullable=True, comment='昵称')

    # 枚举字段
    gender: Mapped[int] = mapped_column(Integer, nullable=False, comment='性别:1-男;2-女;3-其他;')
    department: Mapped[int] = mapped_column(Integer, nullable=False,
                                          comment='部门:1-测试部门;2-开发部门;3-运维部门;4-产品部门;5-其他部门;')

    # 权限字段
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment='是否激活;')
    is_manager: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment='是否管理员;')
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, comment='是否超级管理员;')

    # 扩展字段
    avatar: Mapped[str] = mapped_column(String(255), nullable=True, comment='头像')

    # 审计字段
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment='软删除标记')
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, comment='删除时间')
    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment='最后登录时间')
    login_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0, comment='登录次数')

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    projects = relationship("Project", back_populates="owner")
    access_tokens = relationship("AccessToken", back_populates="user")

    def __repr__(self):
        return f'<User(id={self.id}, phone={self.phone})>'


class Project(Base):
    """项目模型"""
    __tablename__ = "api_projects"
    __table_args__ = {'comment': 'API测试项目表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='项目名称')
    description = Column(Text, comment='项目描述')
    tags = Column(JSON, default=list, comment='自定义标签')
    color = Column(String(20), nullable=True, comment='主题色')  # 项目卡片背景色
    owner_id = Column(Integer, ForeignKey("users.id"), comment='关联的用户ID')
    is_public = Column(Boolean, default=False, comment='是否公开')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    owner = relationship("User", back_populates="projects")
    environments = relationship("Environment", back_populates="project")
    interface_collections = relationship("InterfaceCollection", back_populates="project")
    test_cases = relationship("TestCase", back_populates="project")
    execution_sets = relationship("ExecutionSet", back_populates="project")
    parameter_sets = relationship("ParameterSet", back_populates="project")
    reports = relationship("Report", back_populates="project")


class AiImportPreview(Base):
    """AI 导入临时预览模型。"""
    __tablename__ = "api_ai_import_previews"
    __table_args__ = {'comment': 'AI导入临时预览表'}

    id = Column(String(64), primary_key=True, comment='预览标识')
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment='所属用户ID')
    project_id = Column(Integer, ForeignKey("api_projects.id"), nullable=False, index=True, comment='所属项目ID')
    payload = Column(JSON, nullable=False, comment='预览内容')
    stage = Column(String(32), nullable=False, default='parsed', comment='预览阶段')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    last_access_at = Column(DateTime(timezone=True), default=beijing_now, comment='最近访问时间')
    expires_at = Column(DateTime(timezone=True), nullable=False, comment='过期时间')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')


class Environment(Base):
    """环境模型"""
    __tablename__ = "api_environments"
    __table_args__ = {'comment': 'API测试环境表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='环境名称')
    base_url = Column(String(255), nullable=False, comment='基础URL')
    port = Column(Integer, nullable=True, comment='端口号')
    timeout = Column(Integer, nullable=True, comment='超时时间(秒)')
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    global_variables = Column(JSON, default=dict, comment='全局变量')
    global_headers = Column(JSON, default=dict, comment='全局请求头')
    token_config = Column(JSON, default=dict, comment='Token提取配置: {url, method, jsonpath, body, headers}')
    extracted_token = Column(String(500), nullable=True, comment='最近一次提取的Token值')
    proxy_config = Column(JSON, default=dict, comment='代理配置: {enabled, items:[{name, scheme, url, enabled, priority}]}')
    service_config = Column(JSON, default=dict, comment='服务配置: {items:[{key, name, path_prefix, enabled, description}]}')
    proxy_http = Column(String(255), nullable=True, comment='HTTP代理地址')
    proxy_https = Column(String(255), nullable=True, comment='HTTPS代理地址')
    is_default = Column(Boolean, default=False, comment='是否为默认环境')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="environments")
    creator = relationship("User")


class InterfaceCollection(Base):
    """接口集模型"""
    __tablename__ = "api_interface_collections"
    __table_args__ = {'comment': '接口集目录表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='接口集名称')
    description = Column(Text, nullable=True, comment='接口集描述')
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    parent_id = Column(Integer, ForeignKey("api_interface_collections.id"), nullable=True, comment='父级目录ID')
    source = Column(String(255), nullable=True, comment='导入来源标识')
    sort_order = Column(Integer, default=0, comment='排序号')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="interface_collections")
    interfaces = relationship("Interface", back_populates="collection")
    children = relationship("InterfaceCollection", backref="parent", remote_side=[id], order_by="InterfaceCollection.sort_order")


class Interface(Base):
    """接口模型"""
    __tablename__ = "api_interfaces"
    __table_args__ = {'comment': '接口定义表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='接口名称')
    method = Column(String(10), nullable=False, comment='请求方法')  # GET, POST, PUT, DELETE等
    url = Column(String(500), nullable=False, comment='请求URL路径')  # URL路径
    description = Column(Text, nullable=True, comment='接口描述')
    tags = Column(JSON, default=list, comment='标签列表')  # 标签列表
    source = Column(String(255), nullable=True, comment='导入来源标识')
    source_operation_id = Column(String(255), nullable=True, comment='导入时的operationId')
    definition_fingerprint = Column(String(64), nullable=True, comment='请求响应结构摘要指纹')
    service_key = Column(String(100), nullable=True, comment='所属服务标识，对应环境 service_config.items[].key')
    collection_id = Column(Integer, ForeignKey("api_interface_collections.id"), comment='关联的接口集ID')
    query_params = Column(JSON, default=list, comment='查询参数')  # Query参数
    path_params = Column(JSON, default=list, comment='路径参数')  # Path参数
    body_type = Column(String(20), nullable=True, comment='请求体类型')  # raw, form-data, etc.
    body_content = Column(MEDIUMTEXT, nullable=True, comment='请求体内容')  # 请求体内容（最大16MB）
    body_schema_types = Column(JSON, default=dict, comment='Body字段类型映射')
    headers = Column(JSON, default=list, comment='请求头列表')  # 请求头
    pre_script = Column(Text, nullable=True, comment='前置脚本')  # 前置脚本
    post_script = Column(Text, nullable=True, comment='后置脚本')  # 后置脚本
    response_example = Column(Text, nullable=True, comment='响应示例')  # 响应示例
    workflow_status = Column(String(20), nullable=False, default='pending', comment='接口工作状态：pending待处理 / done已处理')
    pending_reason = Column(String(30), nullable=True, comment='接口待处理原因：new新增 / changed请求定义变化 / legacy存量待确认')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='修改人ID')

    # 关系
    collection = relationship("InterfaceCollection", back_populates="interfaces")
    creator = relationship("User", foreign_keys=[created_by])
    modifier = relationship("User", foreign_keys=[updated_by])
    test_cases = relationship("TestCase", back_populates="interface")


class TestCase(Base):
    """用例模型"""
    __tablename__ = "api_test_cases"
    __table_args__ = {'comment': 'API测试用例表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='用例名称')
    description = Column(Text, nullable=True, comment='用例描述')
    priority = Column(String(20), default="high", comment='优先级: low/medium/high')  # low, medium, high
    owner = Column(String(100), nullable=True, comment='负责人')  # 负责人
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    collection_id = Column(Integer, nullable=True, comment='历史用例集ID，当前用例直接关联接口')
    interface_id = Column(Integer, ForeignKey("api_interfaces.id"), nullable=True, comment='关联的接口ID')
    param_overrides = Column(JSON, default=dict, comment='用例级参数覆盖')
    script = Column(Text, nullable=True, comment='用例级脚本')
    assertions = Column(JSON, default=list, comment='用例断言配置')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='创建人ID')
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='修改人ID')
    last_run_at = Column(DateTime(timezone=True), nullable=True, comment='最后执行时间')
    last_run_status = Column(String(20), nullable=True, comment='最后执行状态(success/failed)')
    confirm_status = Column(String(20), nullable=False, default='pending', comment='用例确认状态：pending待确认 / confirmed已确认')
    confirm_reason = Column(String(30), nullable=True, comment='用例待确认原因：ai_generated AI生成 / manual手动新增 / interface_changed关联接口变化')

    # 关系
    project = relationship("Project", back_populates="test_cases")
    interface = relationship("Interface", back_populates="test_cases")
    creator = relationship("User", foreign_keys=[created_by])
    modifier = relationship("User", foreign_keys=[updated_by])


class ParameterSet(Base):
    """参数集模型"""
    __tablename__ = "api_parameter_sets"
    __table_args__ = {'comment': '参数集表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='参数集名称')
    description = Column(Text, nullable=True, comment='参数集描述')
    project_id = Column(Integer, ForeignKey("api_projects.id"), comment='关联的项目ID')
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='关联的创建人ID')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    # 关系
    project = relationship("Project", back_populates="parameter_sets")
    creator = relationship("User")
    items = relationship("ParameterItem", back_populates="parameter_set",
                         order_by="ParameterItem.sort_order",
                         lazy="selectin")


class ParameterItem(Base):
    """参数项模型"""
    __tablename__ = "api_parameter_items"
    __table_args__ = {'comment': '参数项表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    parameter_set_id = Column(Integer, ForeignKey("api_parameter_sets.id"), comment='关联的参数集ID')
    display_name = Column(String(100), nullable=False, comment='中文名称')
    key = Column(String(100), nullable=False, comment='参数键名')
    value = Column(Text, nullable=False, comment='参数值')
    type = Column(String(20), default="string", comment='类型: string/int/float/bool/list/object')
    type_source = Column(String(20), default="manual", comment='类型来源: schema/manual/inferred/default')
    description = Column(Text, nullable=True, comment='参数描述')
    sort_order = Column(Integer, default=0, comment='排序号')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')

    # 关系
    parameter_set = relationship("ParameterSet", back_populates="items")


class AccessToken(Base):
    """访问令牌模型"""
    __tablename__ = "access_tokens"
    __table_args__ = {'comment': '访问令牌表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    token = Column(String(255), unique=True, index=True, nullable=False, comment='访问令牌')
    user_id = Column(Integer, ForeignKey("users.id"), comment='关联的用户ID')
    name = Column(String(100), nullable=True, comment='令牌名称')  # 令牌名称
    is_active = Column(Boolean, default=True, comment='是否激活')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    expires_at = Column(DateTime(timezone=True), nullable=True, comment='过期时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')

    # 关系
    user = relationship("User", back_populates="access_tokens")


# ========== 问题反馈模型 ==========

class Feedback(Base):
    """问题反馈"""
    __tablename__ = "feedbacks"
    __table_args__ = {'comment': '用户反馈表'}

    id = Column(Integer, primary_key=True, index=True, comment='主键ID')
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment='反馈人')
    type = Column(String(20), default='bug', comment='反馈类型: bug/suggestion/other')
    title = Column(String(200), nullable=False, comment='反馈标题')
    content = Column(Text, nullable=False, comment='反馈内容')
    page_url = Column(String(500), nullable=True, comment='页面路径')
    image_urls = Column(JSON, nullable=True, comment='截图URL列表')
    status = Column(String(20), default='pending', comment='状态: pending/processing/resolved')
    admin_reply = Column(Text, nullable=True, comment='管理员回复')
    interaction_logs = Column(JSON, nullable=True, comment='反馈互动记录')
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment='处理人')
    resolved_at = Column(DateTime(timezone=True), nullable=True, comment='处理时间')
    reply_read_at = Column(DateTime(timezone=True), nullable=True, comment='提交人阅读回复时间')
    reopen_read_at = Column(DateTime(timezone=True), nullable=True, comment='处理人阅读重新打开时间')
    is_deleted = Column(Boolean, default=False, comment='软删除标记')
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment='删除时间')
    created_at = Column(DateTime(timezone=True), default=beijing_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=beijing_now, onupdate=beijing_now, comment='更新时间')

    user = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
