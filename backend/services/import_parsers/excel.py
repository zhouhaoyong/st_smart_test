"""
Excel xlsx 接口清单解析。
Excel 导入的统一解析入口。
"""
import io
import json

from core.response import UnifiedException


# ====== Excel xlsx 接口导入 ======

_INTERFACE_COLUMN_MAP = {
    'name':         ['接口名称', '名称', '接口名', 'name', '接口'],
    'method':       ['请求方式', '请求方法', '方法', 'method', '方式', 'HTTP方法'],
    'url':          ['请求URL', '接口地址', 'URL', 'url', '地址', '路径', 'path', '接口路径'],
    'description':  ['接口描述', '描述', '说明', 'description', 'desc', '备注', '功能说明', 'remark'],
    'tags':         ['标签', 'tags', 'tag', '分类', '模块', 'module', '目录', '所属模块', '接口模块', '一级目录', '二级目录'],
    'headers':      ['请求头', 'headers', 'header', 'Header'],
    'body_type':    ['请求体类型', 'Body类型', 'body_type', '参数类型'],
    'body_content': ['请求体', '请求参数', 'Body', 'body', 'body_content', '参数', '入参', '请求数据'],
    'response_example': ['响应示例', '返回示例', '响应体', '返回体', 'response_example', 'response_body'],
    'query_params': ['Query参数', '查询参数', 'query_params', 'URL参数', 'Params', 'params'],
    'pre_script':   ['前置脚本', 'pre_script', 'PreScript'],
    'post_script':  ['后置脚本', 'post_script', 'PostScript'],
}


def _normalize_interface_column(raw: str) -> str | None:
    """将 Excel 表头映射为接口标准字段名"""
    cleaned = raw.strip().lower().replace('\n', '').replace('\r', '').replace(' ', '').replace('（', '(').replace('）', ')')
    if not cleaned:
        return None

    # 精确匹配
    for field, aliases in _INTERFACE_COLUMN_MAP.items():
        if cleaned in [a.lower().replace(' ', '') for a in aliases]:
            return field

    # 关键词包含匹配
    for field in ['name', 'method', 'url', 'description', 'body_content', 'response_example', 'headers', 'tags', 'query_params', 'pre_script', 'post_script']:
        for alias in _INTERFACE_COLUMN_MAP.get(field, []):
            if alias.lower().replace(' ', '') in cleaned:
                return field

    return None


def _parse_excel_interfaces(file_content: bytes) -> dict:
    """解析 xlsx 内的全部接口工作表，返回统一的模块结构。"""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_content), read_only=False, data_only=True)
    if not wb.worksheets:
        raise UnifiedException(code=400, message="Excel 文件中没有可用的工作表")

    modules: dict[tuple[str, str], dict] = {}
    default_module = '默认模块'

    for ws in wb.worksheets:
        sheet_name = (ws.title or '').strip() or '未命名工作表'
        rows_iter = list(ws.iter_rows(values_only=True))
        if not rows_iter:
            continue

        # 没有“接口名称”或“请求URL”的工作表视为说明页/辅助页，例如模板中的“填写说明”。
        header_row = rows_iter[0]
        col_map: dict[int, str] = {}
        for idx, cell in enumerate(header_row):
            if cell is None:
                continue
            field = _normalize_interface_column(str(cell).strip())
            if field and field not in col_map.values():
                col_map[idx] = field

        fields = set(col_map.values())
        if 'name' not in fields and 'url' not in fields:
            continue

        missing_labels = [
            label for field, label in (('name', '接口名称'), ('url', '请求URL'))
            if field not in fields
        ]
        if missing_labels:
            recognized = ', '.join(sorted(col_map.values())) if col_map else '无'
            raise UnifiedException(
                code=400,
                message=(
                    f"工作表「{sheet_name}」缺少必要列「{'、'.join(missing_labels)}」"
                    f"。已识别列: {recognized}"
                ),
            )
        if len(rows_iter) < 2:
            raise UnifiedException(
                code=400,
                message=f"工作表「{sheet_name}」至少需要包含表头和 1 行数据",
            )

        last_module_name = ''
        for row in rows_iter[1:]:
            record: dict[str, str | list | dict | None] = {
                'name': '',
                'method': 'GET',
                'url': '',
                'description': '',
                'tags': [],
                'headers': [],
                'query_params': [],
                'body_type': 'json',
                'body_content': '',
                'body_schema_types': {},
                'body_required_fields': [],
                'response_example': '',
                'pre_script': '',
                'post_script': '',
            }

            for col_idx, field in col_map.items():
                val = row[col_idx] if col_idx < len(row) else None
                text = str(val).strip() if val is not None else ''

                if field == 'method':
                    text = text.upper()
                    if text not in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'):
                        text = 'GET' if not text else text
                    record[field] = text
                elif field == 'tags':
                    record[field] = [t.strip() for t in text.split(',') if t.strip()] if text else []
                elif field in ('headers', 'query_params'):
                    record[field] = _parse_excel_json_field(text)
                elif field in ('body_content', 'response_example', 'pre_script', 'post_script', 'description', 'url', 'name'):
                    record[field] = text
                elif field == 'body_type':
                    if text and text.lower() in ('json', 'form', 'form-data', 'x-www-form-urlencoded'):
                        record[field] = 'form' if 'form' in text.lower() else 'json'
                else:
                    record[field] = text if text else None

            # 跳过当前工作表中的空行，其他工作表仍可继续导入。
            if not record['name'] or not record['url']:
                continue

            # 标签作为一级目录，工作表名称作为二级目录；未填写标签时沿用当前工作表的上一个标签，
            # 整个工作表都没有标签时归入“默认模块”。
            tags_list = record.get('tags') or []
            if isinstance(tags_list, list) and tags_list:
                module_name = tags_list[0]
            else:
                module_name = last_module_name or default_module

            if module_name:
                last_module_name = module_name

            # 同一标签在不同工作表中也必须拆成不同的二级目录。
            module_key = (module_name, sheet_name)
            if module_key not in modules:
                modules[module_key] = {
                    'level1_name': module_name,
                    'level2_name': sheet_name,
                    'interfaces': [],
                }

            # 清理 tags（去掉用作一级目录的第一个标签）
            if isinstance(record['tags'], list) and len(record['tags']) > 1:
                record['tags'] = record['tags'][1:]

            modules[module_key]['interfaces'].append(record)

    if not modules:
        raise UnifiedException(code=400, message="Excel 中未解析到有效接口数据，请检查内容")

    total = sum(len(m['interfaces']) for m in modules.values())
    return {"modules": list(modules.values()), "total_interfaces": total, "format": "excel"}


# ====== Excel 模板生成（供「下载 Excel 模板」使用） ======
# 表头与 _INTERFACE_COLUMN_MAP 同源：这里只列每个字段的“标准表头”，解析时其别名仍可识别。
# 顺序即模板列顺序；必填列在前。
_TEMPLATE_COLUMNS = [
    ("接口名称", "查询用户列表", "创建用户"),
    ("请求方式", "GET", "POST"),
    ("请求URL", "/api/users", "/api/users"),
    ("标签", "用户管理", "用户管理"),  # 首个标签作为一级目录/模块，多个用英文逗号分隔
    ("接口描述", "分页查询用户列表", "新建一个用户"),
    ("请求头", '{"Content-Type": "application/json"}', '{"Content-Type": "application/json"}'),
    ("请求体类型", "json", "json"),
    ("请求体", "", '{"name": "张三", "age": 18}'),
    ("Query参数", '{"page": "1", "size": "10"}', ""),
]

_TEMPLATE_NOTES = [
    ("列名", "是否必填", "说明"),
    ("接口名称", "必填", "接口的中文名称"),
    ("请求方式", "选填", "GET / POST / PUT / DELETE / PATCH，缺省按 GET"),
    ("请求URL", "必填", "接口路径或完整地址，如 /api/users"),
    ("标签", "选填", "首个标签作为一级目录（模块）；多个标签用英文逗号分隔；工作表名称作为二级目录"),
    ("接口描述", "选填", "接口用途说明"),
    ("请求头", "选填", 'JSON 对象或每行 key:value，如 {"Content-Type":"application/json"}'),
    ("请求体类型", "选填", "json 或 form，缺省 json"),
    ("请求体", "选填", "JSON 字符串，如 {\"name\":\"张三\"}"),
    ("Query参数", "选填", 'JSON 对象或每行 key:value，如 {"page":"1"}'),
    ("", "", ""),
    ("提示", "", "表头名称支持常见别名（如「请求方法」「接口地址」等）；一个文件可填写多个接口工作表；删除示例行后填写自己的接口即可。"),
]


def build_excel_template() -> bytes:
    """生成 Excel 接口清单导入模板（首个工作表为接口清单，另附填写说明）。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = "接口清单"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="409EFF")
    center = Alignment(horizontal="center", vertical="center")

    headers = [c[0] for c in _TEMPLATE_COLUMNS]
    ws.append(headers)
    for col_idx, cell in enumerate(ws[1], 1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        ws.column_dimensions[cell.column_letter].width = max(14, len(str(headers[col_idx - 1])) * 2 + 6)

    # 两行示例
    ws.append([c[1] for c in _TEMPLATE_COLUMNS])
    ws.append([c[2] for c in _TEMPLATE_COLUMNS])
    ws.freeze_panes = "A2"

    # 填写说明（解析器会忽略没有“接口名称”和“请求URL”必要列的辅助工作表）
    note_ws = wb.create_sheet("填写说明")
    for row in _TEMPLATE_NOTES:
        note_ws.append(list(row))
    for cell in note_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
    note_ws.column_dimensions["A"].width = 14
    note_ws.column_dimensions["B"].width = 10
    note_ws.column_dimensions["C"].width = 60

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _parse_excel_json_field(text: str) -> list[dict] | None:
    """尝试将 Excel 单元格内容解析为 JSON 结构，失败则返回 None"""
    if not text or not text.strip():
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [{"key": k, "value": str(v)} for k, v in parsed.items()]
        return []
    except (json.JSONDecodeError, TypeError):
        pass
    # 尝试 key:value / key=value 格式
    result = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        for sep in (': ', ':', '=', '：'):
            if sep in line:
                k, v = line.split(sep, 1)
                result.append({"key": k.strip(), "value": v.strip()})
                break
        else:
            result.append({"key": line, "value": ""})
    return result if result else []
