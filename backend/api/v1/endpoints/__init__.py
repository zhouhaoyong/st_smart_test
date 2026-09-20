"""
API v1 endpoints router
"""
from fastapi import APIRouter
from api.v1.endpoints.auth import router as auth_router
from api.v1.endpoints.users import router as users_router
from api.v1.endpoints.projects import router as projects_router
from api.v1.endpoints.environments import router as environments_router
from api.v1.endpoints.collections import router as collections_router
from api.v1.endpoints.interfaces import router as interfaces_router
from api.v1.endpoints.testcases import router as testcases_router
from api.v1.endpoints.executions import router as executions_router
from api.v1.endpoints.reports import router as reports_router
from api.v1.endpoints.navigation import router as navigation_router
from api.v1.endpoints.tools import router as tools_router
from api.v1.endpoints.executor import router as executor_router
from api.v1.endpoints.import_api import router as import_router
from api.v1.endpoints.import_ai import router as import_ai_router
from api.v1.endpoints.audit import router as audit_router
from api.v1.endpoints.cleanup import router as cleanup_router
from api.v1.endpoints.parameter_sets import router as parameter_sets_router
from api.v1.endpoints.feedbacks import router as feedbacks_router
from api.v1.endpoints.schedule_policies import router as schedule_policies_router
from api.v1.endpoints.ai import router as ai_router
from api.v1.endpoints.message_config import router as message_config_router
from api.v1.endpoints.test_workbench import router as test_workbench_router

api_router = APIRouter()

# 注册各个模块的路由
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(users_router, prefix="/users", tags=["用户管理"])
api_router.include_router(projects_router, prefix="/projects", tags=["项目管理"])
api_router.include_router(environments_router, prefix="/environments", tags=["环境管理"])
api_router.include_router(collections_router, prefix="/collections", tags=["接口集管理"])
api_router.include_router(interfaces_router, prefix="/interfaces", tags=["接口管理"])
api_router.include_router(testcases_router, prefix="/testcases", tags=["用例管理"])
api_router.include_router(executions_router, prefix="/executions", tags=["执行集管理"])
api_router.include_router(reports_router, prefix="/reports", tags=["测试报告"])
api_router.include_router(navigation_router, prefix="/tools", tags=["导航管理"])
api_router.include_router(tools_router, prefix="", tags=["工具箱"])
api_router.include_router(executor_router, tags=["请求执行器"])
api_router.include_router(import_router, tags=["导入"])
api_router.include_router(import_ai_router, tags=["接口列表 AI 生成用例"])
api_router.include_router(audit_router, prefix="/audit", tags=["审计日志"])
api_router.include_router(cleanup_router, prefix="/cleanup", tags=["数据清理"])
api_router.include_router(parameter_sets_router, prefix="/parameter-sets", tags=["参数集管理"])
api_router.include_router(feedbacks_router, tags=["问题反馈"])
api_router.include_router(schedule_policies_router, prefix="/schedule-policies", tags=["执行策略"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI模型&配额"])
api_router.include_router(message_config_router, prefix="/message-config", tags=["平台消息配置"])
api_router.include_router(test_workbench_router, prefix="/test-workbench", tags=["测试工作台"])
