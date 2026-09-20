"""XMind 转换 / 生成工具接口。"""
from __future__ import annotations

import zipfile as _zipfile

from services.xmind_service import (
    generate_csv,
    generate_sample_excel,
    generate_template,
    generate_xlsx,
    generate_xmind_bytes,
    parse_excel_to_rows,
    parse_xmind,
)

from ._shared import (
    APIRouter,
    AsyncSession,
    BaseModel,
    Depends,
    File,
    Request,
    StreamingResponse,
    UnifiedException,
    UploadFile,
    get_current_active_user,
    get_db,
    log_operation,
    success_response,
)

router = APIRouter()


# ====== XMind 转换工具 ======


class XmindExportRequest(BaseModel):
    rows: list
    format: str = "xlsx"  # "csv" 或 "xlsx"


@router.post("/xmind/upload")
async def xmind_upload(
    file: UploadFile = File(...),
    current_user=Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """上传 .xmind 文件并解析，返回结构化数据"""
    # 校验文件扩展名
    if not file.filename or not file.filename.lower().endswith('.xmind'):
        raise UnifiedException(code=400, message="仅支持 .xmind 文件")

    # 校验文件大小（10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise UnifiedException(code=400, message="文件不能超过 10MB")

    try:
        rows = parse_xmind(content)
        # 审计日志
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="Xmind转换工具",
            operation="上传",
            target_name=file.filename,
            description=f"上传并解析 XMind 文件：{file.filename}，共解析 {len(rows)} 条用例",
            details={"filename": file.filename, "row_count": len(rows)},
            ip_address=request.client.host if request and request.client else None,
        )
        return success_response(data={
            "rows": rows,
            "total": len(rows),
        }, message=f"解析成功，共 {len(rows)} 条数据")
    except ValueError as e:
        raise UnifiedException(code=400, message=str(e))
    except _zipfile.BadZipFile:
        raise UnifiedException(code=400, message="文件格式错误，无法解压")
    except Exception as e:
        raise UnifiedException(code=400, message=f"解析失败: {str(e)}")


@router.post("/xmind/export")
async def xmind_export(
    data: XmindExportRequest,
    current_user=Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """根据解析数据生成 CSV 或 Excel 文件"""
    rows = data.rows
    fmt = (data.format or "xlsx").lower()

    if not rows:
        raise UnifiedException(code=400, message="数据为空")

    ext = "csv" if fmt == "csv" else "xlsx"
    # 审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="Xmind转换工具",
        operation="下载",
        target_name=f"testcases.{ext}",
        description=f"导出用例文件：testcases.{ext}，共 {len(rows)} 条用例",
        details={"format": fmt, "row_count": len(rows)},
        ip_address=request.client.host if request and request.client else None,
    )

    if fmt == "csv":
        csv_bytes = generate_csv(rows)
        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="testcases.csv"',
                "Content-Type": "text/csv; charset=utf-8-sig",
            },
        )
    elif fmt == "xlsx":
        xlsx_bytes = generate_xlsx(rows)
        return StreamingResponse(
            iter([xlsx_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="testcases.xlsx"',
            },
        )
    else:
        raise UnifiedException(code=400, message="不支持的导出格式，请选择 csv 或 xlsx")


@router.get("/xmind/template")
async def xmind_download_template(
    current_user=Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """下载 XMind 模板文件，包含正确的4层结构示例"""
    # 审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="Xmind转换工具",
        operation="下载",
        target_name="xmind_template.xmind",
        description="下载 XMind 模板文件",
        details={"type": "template"},
        ip_address=request.client.host if request and request.client else None,
    )
    template_bytes = generate_template()
    return StreamingResponse(
        iter([template_bytes]),
        media_type="application/vnd.xmind.workbook",
        headers={
            "Content-Disposition": 'attachment; filename="xmind_template.xmind"',
        },
    )


class XmindGenerateMetadata(BaseModel):
    source_type: str = "excel"  # 输入类型：excel（后续可扩展 text/markdown/online_doc）
    root_title: str = "需求清单"


@router.post("/xmind/generate")
async def xmind_generate(
    file: UploadFile = File(...),
    source_type: str = "excel",
    root_title: str = "需求清单",
    current_user=Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    将需求清单生成 XMind 文件。
    当前支持 Excel（.xlsx/.xls），预留 source_type 参数用于后续扩展文本/Markdown/在线文档等其他输入方式。
    """
    supported_types = ("excel",)
    if source_type not in supported_types:
        raise UnifiedException(code=400, message=f"暂不支持的输入类型: {source_type}，当前支持: {', '.join(supported_types)}")

    if not file.filename:
        raise UnifiedException(code=400, message="请上传文件")

    # 校验文件大小（10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise UnifiedException(code=400, message="文件不能超过 10MB")

    if source_type == "excel":
        # 校验扩展名
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ('xlsx', 'xls'):
            raise UnifiedException(code=400, message="仅支持 .xlsx / .xls 格式的 Excel 文件")

        try:
            rows, warnings_list = parse_excel_to_rows(content)
        except ValueError as e:
            raise UnifiedException(code=400, message=str(e))

        try:
            xmind_bytes = generate_xmind_bytes(rows, root_title)
        except Exception as e:
            raise UnifiedException(code=400, message=f"生成 XMind 文件失败: {e}")

        # 生成文件名
        base_name = file.filename.rsplit('.', 1)[0] if '.' in (file.filename or '') else 'testcases'
        download_name = f"{base_name}.xmind"

        # 审计日志
        warn_summary = f"，{len(warnings_list)} 条警告" if warnings_list else ""
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="Xmind生成工具",
            operation="生成Xmind",
            target_name=file.filename,
            description=f"需求清单生成 XMind：{file.filename}，共 {len(rows)} 条用例{warn_summary}",
            details={
                "source_type": source_type,
                "filename": file.filename,
                "row_count": len(rows),
                "warnings": warnings_list[:20] if warnings_list else [],
            },
            ip_address=request.client.host if request and request.client else None,
        )

        return StreamingResponse(
            iter([xmind_bytes]),
            media_type="application/vnd.xmind.workbook",
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"',
            },
        )


@router.get("/xmind/sample-excel")
async def xmind_download_sample_excel(
    current_user=Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """下载需求清单示例 Excel，展示正确的列格式"""
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="Xmind生成工具",
        operation="下载",
        target_name="requirement_sample.xlsx",
        description="下载需求清单示例 Excel",
        details={"type": "sample_excel"},
        ip_address=request.client.host if request and request.client else None,
    )
    excel_bytes = generate_sample_excel()
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="requirement_sample.xlsx"',
        },
    )
