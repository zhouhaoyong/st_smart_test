"""
导入接口 — OpenAPI 3.0 / Swagger 2.0 / Postman Collection v2.1 / Excel xlsx
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime, timezone
from db.session import get_db
from models.models import InterfaceCollection, Interface, TestCase, User, Project
from services.api_test_workflow import (
    TEST_CASE_CONFIRM_PENDING,
    TEST_CASE_CONFIRM_REASON_MANUAL,
    apply_import_workflow_state,
)
from core.security import get_current_active_user
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from services.import_parsers import (
    DocumentParseError,
    MAX_FILE_SIZE,
    MAX_XLSX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    _detect_format,
    _parse_excel_interfaces,
    _parse_openapi,
    _parse_postman,
    build_excel_template,
    parse_document_bytes,
    split_invalid_request_bodies,
)
from core.permissions import ensure_project_asset_manage
from services.file_import_dedup import (
    CHANGE_NAME,
    classify_import_interfaces,
    diff_existing_interface,
    match_existing_interface,
    merge_case_overrides,
)
from services.interface_structure import interface_structure_fingerprint
from utils.audit_logger import build_batch_audit_description, log_interface_import, log_user_operation

router = APIRouter(prefix="/import", tags=["导入"])

# 判重口径由公共模块统一，文件导入与 cURL 导入不再各自实现一套


# ====== 端点 ======

class PreviewItem(BaseModel):
    module_name: str
    interface_count: int
    interfaces: list


class ParseResult(BaseModel):
    format: str
    modules: list
    total_interfaces: int


class ImportItem(BaseModel):
    module_name: str
    interfaces: list  # each a dict of interface fields


class ExecuteImportRequest(BaseModel):
    project_id: int
    source: str
    selected_modules: List[dict] = []
    create_test_cases: bool = False
    # 命中已有接口且内容有差异时：True 按文档覆盖，False 保留平台上的现有接口只导入新接口
    # 默认 True 保持原有行为，未传该字段的调用方不受影响
    overwrite_existing: bool = True
    # 新增：全局一级目录设置
    global_level1_collection_id: int | None = None  # 选择现有接口集作为一级
    global_level1_name: str | None = None  # 自定义一级目录名
    # 用户在第一步选「新建接口集」时给出的层级路径，从根往下，逐级不存在就建
    global_level1_path: List[str] = []
    # 后端以此作为本次真正处理范围的权威条件；缺省保持全量兼容。
    import_mode: Literal["full", "incremental"] = "full"


class CheckDuplicatesRequest(BaseModel):
    """解析完成后、真正导入之前，先问一次"这些接口在平台上是否已存在、有没有变化"。

    不需要目标接口集：判重与接口集无关，导入模式由后端决定返回的接口范围。
    """
    project_id: int
    selected_modules: List[dict] = []
    import_mode: Literal["full", "incremental"] = "full"


class CurlBatchInterface(BaseModel):
    """批量 cURL 导入中的接口预览项。"""
    key: str
    name: str
    method: str
    url: str
    collection_id: int | None = None
    query_params: list = Field(default_factory=list)
    path_params: list = Field(default_factory=list)
    body_type: str | None = None
    body_content: str | None = None
    headers: list = Field(default_factory=list)
    pre_script: str | None = None
    post_script: str | None = None
    service_key: str | None = None


class CurlBatchCase(BaseModel):
    """批量 cURL 导入中的用例预览项。"""
    interface_key: str
    name: str
    param_overrides: dict = Field(default_factory=dict)
    priority: str = "high"
    assertions: list | None = None


class CurlBatchImportRequest(BaseModel):
    """一次保存批量 cURL 导入的接口和用例。"""
    project_id: int
    collection_id: int | None = None  # 选择现有接口集
    # 选「新建接口集」时给出的层级路径，从根往下，逐级不存在就建
    collection_path: list[str] = Field(default_factory=list)
    interfaces: list[CurlBatchInterface] = Field(default_factory=list)
    cases: list[CurlBatchCase] = Field(default_factory=list)


@router.post("/parse-url")
async def parse_url(
    url: str = Form(...),
    current_user: User = Depends(get_current_active_user),
):
    """通过 URL 获取并解析文档（暂未开放）"""
    raise UnifiedException(code=400, message="URL 导入暂未开放，请使用文件上传")


@router.get("/excel-template")
async def download_excel_template(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """下载文件导入使用的 Excel 接口清单模板。"""
    content = build_excel_template()
    await log_user_operation(
        db=db,
        user=current_user,
        module="api_import",
        operation="下载",
        target_name="Excel 接口导入模板",
        description="下载接口导入模板",
    )
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="api_import_template.xlsx"'},
    )


@router.post("/parse-file")
async def parse_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """上传文件并解析"""
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in (file.filename or "") else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnifiedException(code=400, message=f"仅支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))} 格式")
    try:
        max_size = MAX_XLSX_FILE_SIZE if ext == ".xlsx" else MAX_FILE_SIZE
        size_error = "xlsx_too_large" if ext == ".xlsx" else "file_too_large"
        contents = await _read_upload_with_limit(file, max_size, size_error)
        result = parse_document_bytes(file.filename, contents)
    except DocumentParseError as exc:
        _raise_document_parse_error(exc)
    valid_result, failed_interfaces = split_invalid_request_bodies(result)
    return _cache_and_respond(
        valid_result,
        require_interfaces=not failed_interfaces or valid_result["total_interfaces"] > 0,
        failed_interfaces=failed_interfaces,
        total_interfaces=result["total_interfaces"],
    )


_parse_cache = {}


async def _read_upload_with_limit(file: UploadFile, max_size: int, reason: str = "file_too_large") -> bytes:
    """流式读取上传文件，超过上限时立即中止，不把超大文件完整放入内存。"""
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(min(1024 * 1024, max_size - total_size + 1))
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise DocumentParseError(reason)
        chunks.append(chunk)
    return b"".join(chunks)


def _raise_document_parse_error(error: DocumentParseError) -> None:
    messages = {
        "xlsx_too_large": f"Excel 文件大小超过 {MAX_XLSX_FILE_SIZE // (1024*1024)}MB 限制",
        "file_too_large": f"文件大小超过 {MAX_FILE_SIZE // (1024*1024)}MB 限制",
        "invalid_encoding": "文件编码错误，请使用 UTF-8",
        "invalid_document": "文件格式错误，无法解析 JSON 或 YAML",
        "invalid_content": "文件内容格式不正确",
        "unknown_format": "无法识别文档格式，请确认是 OpenAPI / Swagger / Postman",
    }
    if error.reason == "xlsx_parse_failed":
        message = f"Excel 解析失败: {error.detail}"
    else:
        message = messages.get(error.reason, error.detail or "文件解析失败")
    raise UnifiedException(code=400, message=message) from error


def _cache_and_respond(
    result: dict,
    *,
    require_interfaces: bool = False,
    failed_interfaces: list[dict] | None = None,
    total_interfaces: int | None = None,
):
    if require_interfaces and result["total_interfaces"] == 0:
        if result["format"] == "excel":
            raise UnifiedException(code=400, message="Excel 文件中未找到任何接口定义")
        raise UnifiedException(code=400, message="文档中未找到任何接口定义")

    import uuid
    cache_id = uuid.uuid4().hex
    _parse_cache[cache_id] = result
    if len(_parse_cache) > 10:
        oldest = sorted(_parse_cache.keys())[:len(_parse_cache) - 10]
        for key in oldest:
            del _parse_cache[key]

    return success_response(data={
        "cache_id": cache_id,
        "format": result["format"],
        "modules": [{
            "level1_name": module["level1_name"],
            "level2_name": module.get("level2_name", ""),
            "interface_count": len(module["interfaces"]),
            "interfaces": module["interfaces"],
        } for module in result["modules"]],
        "total_interfaces": result["total_interfaces"] if total_interfaces is None else total_interfaces,
        "failed_interfaces": failed_interfaces or [],
    })


def _parse_content(content: str, user_id: str):
    """兼容旧调用方的文本解析入口，实际解析统一走文档服务。"""
    try:
        result = parse_document_bytes("upload.json", content.encode("utf-8"))
    except DocumentParseError as exc:
        _raise_document_parse_error(exc)
    return _cache_and_respond(result, require_interfaces=True)


@router.post("/check-duplicates")
async def check_import_duplicates(
    req: CheckDuplicatesRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """预览阶段判重：只读比对，不建接口集、不改任何数据。

    根据导入模式返回对应范围的结论。用户切换模式时重新请求，
    每条结论保留原始 index，前端据此把结论对回当前预览行。
    """
    project = (await db.execute(select(Project).where(Project.id == req.project_id, Project.is_deleted == False))).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    # 判重是项目级的，与本次选定的接口集完全无关：接口集既不参与定位，也不参与变化判定
    result = await classify_import_interfaces(
        db,
        req.project_id,
        req.selected_modules,
        import_mode=req.import_mode,
    )

    # 没有变化的接口在两种模式下都不落库、不建用例，前端要如实告诉用户这批的条数
    result["unchanged_count"] = result["duplicate_count"]
    return success_response(data=result)


@router.post("/execute")
async def execute_import(
    req: ExecuteImportRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """执行文件导入，可按请求选择是否创建基础测试用例。"""
    from models.models import TestCase
    import json as _json

    project_id = req.project_id
    source = req.source or f"import_{beijing_now().strftime('%Y%m%d%H%M%S')}"
    modules_data = req.selected_modules
    create_cases = req.create_test_cases
    overwrite_existing = req.overwrite_existing
    global_level1_id = req.global_level1_collection_id
    global_level1_name = req.global_level1_name
    global_level1_path = [str(name).strip() for name in (req.global_level1_path or []) if str(name).strip()]

    if not modules_data:
        raise UnifiedException(code=400, message="未选择任何要导入的模块")

    project = (await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    if req.import_mode == "incremental":
        # 增量范围由后端按执行时的最新数据重新判定，不能信任前端仅仅隐藏了哪些行。
        classification = await classify_import_interfaces(
            db,
            project_id,
            modules_data,
            import_mode="incremental",
        )
        visible_indexes = {item["index"] for item in classification["items"]}
        scoped_modules = []
        index = 0
        for module in modules_data:
            scoped_interfaces = []
            for iface in module.get("interfaces", []) or []:
                if index in visible_indexes:
                    scoped_interfaces.append(iface)
                index += 1
            if scoped_interfaces:
                scoped_modules.append({**module, "interfaces": scoped_interfaces})
        modules_data = scoped_modules
        if not modules_data:
            raise UnifiedException(code=400, message="没有需要导入的接口")

    # 没落库的接口分成两类分别计数，报告才能说清楚"为什么没导进去"：
    # unchanged 是内容完全一致、两种模式下都不动；preserved 是有变化但用户选了保留
    report = {
        "new_interfaces": 0, "updated_interfaces": 0,
        "unchanged_interfaces": 0, "preserved_interfaces": 0,
        "new_test_cases": 0, "updated_test_cases": 0,
        "new_modules": 0, "updated_modules": 0,
    }

    # 缓存已创建的接口集，避免重复查询
    collection_cache = {}

    async def child_collection(parent_id, name: str):
        """按名称取某一层接口集，没有就建。"""
        cache_key = f"{parent_id or 0}::{name}"
        if cache_key in collection_cache:
            return collection_cache[cache_key]

        query = select(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            InterfaceCollection.name == name,
            InterfaceCollection.is_deleted == False,
        )
        query = query.where(
            InterfaceCollection.parent_id.is_(None) if parent_id is None
            else InterfaceCollection.parent_id == parent_id
        )
        found = (await db.execute(query)).scalars().first()

        if not found:
            found = InterfaceCollection(
                name=name,
                project_id=project_id,
                parent_id=parent_id,
                source=source,
            )
            db.add(found)
            await db.flush()
            report["new_modules"] += 1

        collection_cache[cache_key] = found
        return found

    async def resolve_target_collection(level1_name: str, level2_name: str, use_global_level1: bool):
        """定位或创建落库目录。

        判重是项目级的，只有确实要新建接口时才需要这个目录：命中已有接口一律原地更新，
        整批都是老接口时提前建目录会凭空多出空接口集。
        """
        level1_collection = None

        if use_global_level1 and global_level1_id:
            # 用户在第一步选了已有接口集
            level1_collection = (await db.execute(
                select(InterfaceCollection).where(
                    InterfaceCollection.id == global_level1_id,
                    InterfaceCollection.is_deleted == False
                )
            )).scalars().first()
            if not level1_collection:
                raise UnifiedException(code=400, message=f"选定的上级目录(ID={global_level1_id})不存在")
        elif use_global_level1 and global_level1_path:
            # 用户在第一步选了新建接口集：按给定层级逐级建出来
            for name in global_level1_path:
                level1_collection = await child_collection(
                    level1_collection.id if level1_collection else None, name,
                )
        elif use_global_level1 and global_level1_name:
            # 只给了单个自定义一级目录名的老调用方式
            level1_collection = await child_collection(None, global_level1_name)
        elif not level1_name:
            level1_name = level2_name or "默认模块"

        if not level1_collection:
            level1_collection = await child_collection(None, level1_name)

        if not level2_name:
            return level1_collection
        return await child_collection(level1_collection.id, level2_name)

    try:
        for module_idx, module_data in enumerate(modules_data):
            level1_name = module_data.get("level1_name", "")
            level2_name = module_data.get("level2_name", "")
            interfaces_to_import = module_data.get("interfaces", [])
            use_global_level1 = module_data.get("use_global_level1", False)

            # 目录按需创建：只有真要新建接口时才落目录，整批都命中已有接口时
            # 不该凭空多出空接口集
            target_collection = None

            # === 导入接口 ===
            for iface_data in interfaces_to_import:
                # 项目级判重：换个接口集再导同一份文档，也能认出是同一个接口
                existing_iface = await match_existing_interface(db, project_id, iface_data)

                iface_id = None
                # 这一条这次不落库：接口和它下面的用例都不动
                skip_this_interface = False
                linked_cases = []
                if existing_iface:
                    # 名称、地址、请求方法、请求参数，四项任一不同才算有变化；
                    # 接口集不参与判定，已有接口一律留在它现在的位置
                    change_reasons = diff_existing_interface(existing_iface, iface_data)
                    if not change_reasons:
                        # 内容完全一致：两种模式下都不导入，也不为它新建或更新用例
                        report["unchanged_interfaces"] += 1
                        iface_id = existing_iface.id
                        # 结构已确认一致，顺手把缺失的摘要补上（判重本身实时重算，不依赖它）
                        if not existing_iface.definition_fingerprint:
                            existing_iface.definition_fingerprint = interface_structure_fingerprint(iface_data)
                        skip_this_interface = True
                    elif not overwrite_existing:
                        # 有变化但用户选了保留：接口原样不动，用例也不动
                        report["preserved_interfaces"] += 1
                        iface_id = existing_iface.id
                        skip_this_interface = True
                    else:
                        linked_cases = (await db.execute(
                            select(TestCase).where(
                                TestCase.interface_id == existing_iface.id,
                                TestCase.is_deleted == False,
                            )
                        )).scalars().all()
                        # 只有名称变化时只更新名称，不触碰接口状态、关联用例或其他字段。
                        if set(change_reasons) == {CHANGE_NAME}:
                            existing_iface.name = iface_data.get("name") or existing_iface.name
                            existing_iface.updated_by = current_user.id
                            report["updated_interfaces"] += 1
                            iface_id = existing_iface.id

                        existing_iface.url = iface_data["url"]
                        existing_iface.method = iface_data["method"]
                        existing_iface.name = iface_data.get("name") or existing_iface.name
                        existing_iface.description = iface_data.get("description")
                        existing_iface.tags = iface_data.get("tags", [])
                        existing_iface.query_params = iface_data.get("query_params", [])
                        existing_iface.path_params = iface_data.get("path_params", [])
                        existing_iface.headers = iface_data.get("headers", [])
                        existing_iface.body_type = iface_data.get("body_type")
                        existing_iface.body_content = iface_data.get("body_content")
                        existing_iface.body_schema_types = iface_data.get("body_schema_types", {})
                        if iface_data.get("pre_script") is not None:
                            existing_iface.pre_script = iface_data["pre_script"]
                        if iface_data.get("post_script") is not None:
                            existing_iface.post_script = iface_data["post_script"]
                        existing_iface.source = source
                        existing_iface.source_operation_id = iface_data.get("operation_id")
                        existing_iface.service_key = iface_data.get("service_key") or None
                        existing_iface.definition_fingerprint = interface_structure_fingerprint(iface_data)
                        existing_iface.updated_by = current_user.id
                        # collection_id 刻意不动：文档换了模块名也不搬家，
                        # 已有接口留在用户当前放它的位置
                        for linked_case in linked_cases:
                            linked_case.param_overrides = merge_case_overrides(
                                linked_case.param_overrides, iface_data,
                            )
                            linked_case.updated_by = current_user.id
                            report["updated_test_cases"] += 1
                        report["updated_interfaces"] += 1
                        iface_id = existing_iface.id
                        apply_import_workflow_state(
                            existing_iface,
                            change_reasons=change_reasons,
                            linked_cases=linked_cases,
                        )
                else:
                    # 确实要新建接口时才落目录，避免整批命中已有接口还多出空接口集
                    if target_collection is None:
                        target_collection = await resolve_target_collection(
                            level1_name, level2_name, use_global_level1,
                        )
                    new_iface = Interface(
                        name=iface_data["name"], method=iface_data["method"],
                        url=iface_data["url"], description=iface_data.get("description"),
                        tags=iface_data.get("tags", []), collection_id=target_collection.id,
                        service_key=iface_data.get("service_key") or None,
                        query_params=iface_data.get("query_params", []),
                        path_params=iface_data.get("path_params", []),
                        headers=iface_data.get("headers", []),
                        body_type=iface_data.get("body_type"),
                        body_content=iface_data.get("body_content"),
                        body_schema_types=iface_data.get("body_schema_types", {}),
                        pre_script=iface_data.get("pre_script"),
                        post_script=iface_data.get("post_script"),
                        source=source, source_operation_id=iface_data.get("operation_id"),
                        definition_fingerprint=interface_structure_fingerprint(iface_data),
                        created_by=current_user.id,
                        updated_by=current_user.id,
                    )
                    db.add(new_iface)
                    await db.flush()
                    report["new_interfaces"] += 1
                    iface_id = new_iface.id
                    apply_import_workflow_state(new_iface, is_new=True)

                # 这次没落库的接口一律不碰用例：内容没变化的本来就无可更新，
                # 凭空给它补一条用例既不是用户要的，也和"没有变化就不动"的说法自相矛盾
                if create_cases and iface_id and not skip_this_interface:
                    # 请求定义变化时，当前流程已在上方同步已有用例，避免重复更新和重复计数。
                    if linked_cases:
                        continue

                    tc_name = f"{iface_data['name']}_用例"
                    case_overrides = {
                        "method": iface_data.get("method", "GET"),
                        "url": iface_data.get("url", ""),
                        "headers": iface_data.get("headers", []),
                        "query_params": iface_data.get("query_params", []),
                        "path_params": iface_data.get("path_params", []),
                        "body_type": iface_data.get("body_type"),
                        "body_content": iface_data.get("body_content"),
                        "body_schema_types": iface_data.get("body_schema_types", {}),
                        "pre_script": iface_data.get("pre_script", ""),
                        "post_script": iface_data.get("post_script", ""),
                    }
                    existing_tc = (await db.execute(
                        select(TestCase).where(
                            TestCase.interface_id == iface_id,
                            TestCase.is_deleted == False,
                        )
                    )).scalars().first()

                    if existing_tc:
                        # 已有用例只增不减：补进文档新增的参数，不覆盖用户填过的取值，也不改断言。
                        existing_tc.param_overrides = merge_case_overrides(
                            existing_tc.param_overrides, iface_data,
                        )
                        existing_tc.updated_by = current_user.id
                        report["updated_test_cases"] += 1
                    else:
                        db.add(TestCase(
                            name=tc_name,
                            project_id=project_id,
                            interface_id=iface_id,
                            priority="high",
                            owner=current_user.real_name,
                            param_overrides=case_overrides,
                            assertions=[{
                                "type": "jsonpath",
                                "expression": "$.code",
                                "operator": "eq",
                                "expected": "200",
                                "enabled": True,
                            }],
                            created_by=current_user.id,
                            updated_by=current_user.id,
                        ))
                        report["new_test_cases"] += 1

        await db.commit()

        summary = (
            f"文件导入完成：接口：新增 {report['new_interfaces']} 个，更新 {report['updated_interfaces']} 个；"
            f"用例：新增 {report['new_test_cases']} 个，更新 {report['updated_test_cases']} 个"
        )
        if report["unchanged_interfaces"]:
            summary += f"；没有变化未导入 {report['unchanged_interfaces']} 个"
        if report["preserved_interfaces"]:
            summary += f"；有变化但按增量模式保留 {report['preserved_interfaces']} 个"
        await log_interface_import(
            db=db,
            user=current_user,
            project_id=project_id,
            project_name=project.name,
            source="file",
            source_name=source,
            status="success",
            summary=summary,
            details={"report": report},
            request=request,
        )

        parts = [f"新增 {report['new_interfaces']} 个接口、{report['new_modules']} 个模块"]
        if report['updated_interfaces']:
            parts.append(f"更新 {report['updated_interfaces']} 个接口")
        if report['new_test_cases']:
            parts.append(f"新增 {report['new_test_cases']} 个用例")
        if report['updated_test_cases']:
            parts.append(f"更新 {report['updated_test_cases']} 个用例")
        # 没导进去的两类分别说明，不再合并成一个含糊的"跳过"
        if report['unchanged_interfaces']:
            parts.append(
                f"另有 {report['unchanged_interfaces']} 个接口没有变化，未导入"
            )
        if report['preserved_interfaces']:
            parts.append(
                f"{report['preserved_interfaces']} 个接口有变化，但按增量模式原样保留"
            )

        return success_response(data={
            "report": report,
            "message": "导入完成：" + "，".join(parts),
        })

    except UnifiedException as exc:
        await db.rollback()
        await log_interface_import(
            db=db,
            user=current_user,
            project_id=project_id,
            project_name=project.name if 'project' in locals() and project else None,
            source="file",
            source_name=source,
            status="failed",
            summary="文件导入失败",
            details={"message": str(exc.message)},
            request=request,
        )
        raise
    except Exception as e:
        await db.rollback()
        await log_interface_import(
            db=db,
            user=current_user,
            project_id=project_id,
            project_name=project.name if 'project' in locals() and project else None,
            source="file",
            source_name=source,
            status="failed",
            summary="文件导入失败",
            details={"message": str(e)},
            request=request,
        )
        raise UnifiedException(code=400, message=f"导入失败: {str(e)}")


@router.post("/curl-batch")
async def execute_curl_batch_import(
    req: CurlBatchImportRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """一次保存批量 cURL 导入结果，并只写一条项目级审计。"""
    project = (await db.execute(
        select(Project).where(Project.id == req.project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    collection_path = [str(name).strip() for name in (req.collection_path or []) if str(name).strip()]
    collection = None
    if req.collection_id:
        collection = (await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == req.collection_id,
                InterfaceCollection.project_id == req.project_id,
                InterfaceCollection.is_deleted == False,
            )
        )).scalar_one_or_none()
        if not collection:
            raise UnifiedException(code=400, message="接口集不存在或不属于当前项目")
    elif not collection_path:
        raise UnifiedException(code=400, message="请选择导入到哪个接口集")
    if not req.interfaces:
        raise UnifiedException(code=400, message="没有可导入的接口")

    report = {
        "new_modules": 0,
        "new_interfaces": 0,
        "updated_interfaces": 0,
        "skipped_interfaces": 0,
        "new_test_cases": 0,
        "updated_test_cases": 0,
        "failed_interfaces": 0,
        "failed_test_cases": 0,
    }
    errors: list[dict[str, str]] = []
    interface_by_key: dict[str, Interface] = {}
    seen_names: set[str] = set()

    # 接口集按需定位/创建：整批都命中已有接口时不该凭空多出空接口集
    target_collection = collection
    existing_names: set[str] = set()
    names_loaded = False

    async def ensure_target_collection() -> InterfaceCollection:
        """定位落库接口集；选了新建就按层级路径逐级建出来。"""
        nonlocal target_collection, existing_names, names_loaded
        if target_collection is None:
            parent_id = None
            for level_name in collection_path:
                query = select(InterfaceCollection).where(
                    InterfaceCollection.project_id == req.project_id,
                    InterfaceCollection.name == level_name,
                    InterfaceCollection.is_deleted == False,
                )
                query = query.where(
                    InterfaceCollection.parent_id.is_(None) if parent_id is None
                    else InterfaceCollection.parent_id == parent_id
                )
                found = (await db.execute(query)).scalars().first()
                if not found:
                    found = InterfaceCollection(
                        name=level_name,
                        project_id=req.project_id,
                        parent_id=parent_id,
                        source="curl",
                    )
                    db.add(found)
                    await db.flush()
                    report["new_modules"] += 1
                target_collection = found
                parent_id = found.id
        if not names_loaded:
            rows = (await db.execute(
                select(Interface).where(
                    Interface.collection_id == target_collection.id,
                    Interface.is_deleted == False,
                )
            )).scalars().all()
            existing_names = {str(row.name).strip() for row in rows if row.name}
            names_loaded = True
        return target_collection

    # 本批新建的接口也要参与判重，否则同一批里两条相同命令会建出两个接口
    created_by_route: dict[tuple[str, str, str | None], Interface] = {}

    for item in req.interfaces:
        key = str(item.key or "").strip()
        name = str(item.name or "").strip()
        if not key or not name:
            report["failed_interfaces"] += 1
            errors.append({"type": "interface", "name": name or key or "未命名接口", "error": "接口标识或名称为空"})
            continue
        if key in interface_by_key:
            report["failed_interfaces"] += 1
            errors.append({"type": "interface", "name": name, "error": "批量数据中的接口标识重复"})
            continue
        route = (
            str(item.method or "GET").upper(),
            str(item.url or ""),
            str(item.service_key or "").strip() or None,
        )
        incoming = {
            "url": item.url,
            "method": route[0],
            "query_params": item.query_params,
            "path_params": item.path_params,
            "headers": item.headers,
            "body_type": item.body_type,
            "body_content": item.body_content,
            "service_key": route[2],
        }
        matched = created_by_route.get(route)
        if matched is None:
            # 项目级判重：同一个接口先前导到别的接口集里，这里也不再重复新建
            matched = await match_existing_interface(db, req.project_id, incoming)
        if matched is not None:
            # 名称、地址、请求方法、请求参数任一变化都要按统一口径处理；
            # 只有四项完全一致才跳过，接口位置始终保持不变。
            change_reasons = diff_existing_interface(matched, {**incoming, "name": name})
            if not change_reasons:
                report["skipped_interfaces"] += 1
                if not matched.definition_fingerprint:
                    matched.definition_fingerprint = interface_structure_fingerprint(incoming)
            else:
                if set(change_reasons) == {CHANGE_NAME}:
                    matched.name = name
                    matched.updated_by = current_user.id
                    report["updated_interfaces"] += 1
                    interface_by_key[key] = matched
                    continue
                linked_cases = (await db.execute(
                    select(TestCase).where(
                        TestCase.interface_id == matched.id,
                        TestCase.is_deleted == False,
                    )
                )).scalars().all()
                matched.query_params = item.query_params
                matched.path_params = item.path_params
                matched.body_type = item.body_type
                matched.body_content = item.body_content
                matched.headers = item.headers
                matched.pre_script = item.pre_script
                matched.post_script = item.post_script
                matched.service_key = item.service_key
                matched.definition_fingerprint = interface_structure_fingerprint(incoming)
                matched.updated_by = current_user.id
                report["updated_interfaces"] += 1
                apply_import_workflow_state(
                    matched,
                    change_reasons=change_reasons,
                    linked_cases=linked_cases,
                )
                for linked_case in linked_cases:
                    linked_case.param_overrides = merge_case_overrides(
                        linked_case.param_overrides, incoming,
                    )
                    linked_case.updated_by = current_user.id
                    report["updated_test_cases"] += 1
            interface_by_key[key] = matched
            continue

        # 确实要新建接口时才落目录
        target = await ensure_target_collection()
        if name in existing_names or name in seen_names:
            report["failed_interfaces"] += 1
            errors.append({"type": "interface", "name": name, "error": "该接口集下接口名称已存在"})
            continue

        interface = Interface(
            name=name,
            method=item.method,
            url=item.url,
            collection_id=target.id,
            query_params=item.query_params,
            path_params=item.path_params,
            body_type=item.body_type,
            body_content=item.body_content,
            headers=item.headers,
            pre_script=item.pre_script,
            post_script=item.post_script,
            service_key=item.service_key,
            source="curl",
            definition_fingerprint=interface_structure_fingerprint(incoming),
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(interface)
        apply_import_workflow_state(interface, is_new=True)
        interface_by_key[key] = interface
        created_by_route[route] = interface
        seen_names.add(name)
        report["new_interfaces"] += 1

    await db.flush()

    case_names_by_interface: dict[int, set[str]] = {}
    interface_ids = [item.id for item in interface_by_key.values() if item.id is not None]
    if interface_ids:
        existing_cases_result = await db.execute(
            select(TestCase).where(
                TestCase.interface_id.in_(interface_ids),
                TestCase.is_deleted == False,
            )
        )
        case_names_by_interface = {}
        for existing_case in existing_cases_result.scalars().all():
            case_names_by_interface.setdefault(existing_case.interface_id, set()).add(existing_case.name)

    for case in req.cases:
        interface = interface_by_key.get(str(case.interface_key or "").strip())
        case_name = str(case.name or "").strip()
        if interface is None:
            report["failed_test_cases"] += 1
            errors.append({"type": "test_case", "name": case_name or "未命名用例", "error": "关联接口未导入成功"})
            continue
        names = case_names_by_interface.setdefault(interface.id, set())
        if not case_name or case_name in names:
            report["failed_test_cases"] += 1
            errors.append({"type": "test_case", "name": case_name or "未命名用例", "error": "该接口下用例名称已存在"})
            continue

        db.add(TestCase(
            name=case_name,
            project_id=req.project_id,
            interface_id=interface.id,
            priority=case.priority,
            owner=current_user.real_name,
            param_overrides=case.param_overrides,
            assertions=case.assertions or [{
                "type": "jsonpath",
                "expression": "$.code",
                "operator": "eq",
                "expected": "200",
                "enabled": True,
            }],
            confirm_status=TEST_CASE_CONFIRM_PENDING,
            confirm_reason=TEST_CASE_CONFIRM_REASON_MANUAL,
            created_by=current_user.id,
            updated_by=current_user.id,
        ))
        names.add(case_name)
        report["new_test_cases"] += 1

    report["failed_count"] = len(errors)
    await db.commit()

    handled = report["new_interfaces"] + report["updated_interfaces"] + report["skipped_interfaces"]
    status = "success" if not errors else "partial" if handled or report["new_test_cases"] else "failed"
    summary = build_batch_audit_description(
        project.name,
        "导入",
        "接口",
        report["new_interfaces"],
        {"用例": report["new_test_cases"]},
    )
    if report["updated_interfaces"]:
        summary += f"；更新已有接口 {report['updated_interfaces']} 个"
    if report["skipped_interfaces"]:
        summary += f"；跳过已存在接口 {report['skipped_interfaces']} 个（内容完全相同）"
    await log_interface_import(
        db=db,
        user=current_user,
        project_id=req.project_id,
        project_name=project.name,
        source="curl",
        source_name="批量 cURL 命令",
        status=status,
        summary=summary,
        details={"report": report, "errors": errors},
        request=request,
    )
    return success_response(
        data={
            "new_modules": report["new_modules"],
            "new_interfaces": report["new_interfaces"],
            "updated_interfaces": report["updated_interfaces"],
            "skipped_interfaces": report["skipped_interfaces"],
            "new_test_cases": report["new_test_cases"],
            "updated_test_cases": report["updated_test_cases"],
            "imported_interfaces": report["new_interfaces"],
            "created_cases": report["new_test_cases"],
            "failed_count": report["failed_count"],
            "errors": errors,
        },
        message=summary,
    )
