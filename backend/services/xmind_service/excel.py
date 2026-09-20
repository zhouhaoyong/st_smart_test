"""
Excel / CSV 处理 - 测试用例导出 (CSV/XLSX) 与需求清单 Excel 解析、示例 Excel 生成
"""
from ._shared import *  # noqa: F401,F403  （csv / io / openpyxl 等）

__all__ = [
    'generate_csv',
    'generate_xlsx',
    'parse_excel_to_rows',
    'generate_sample_excel',
]


# ====== CSV 导出 ======

def generate_csv(rows: List[Dict[str, Any]]) -> bytes:
    """生成带 UTF-8 BOM 的 CSV 文件字节"""
    output = io.StringIO()
    # 写入 BOM（Excel 需要 BOM 才能正确识别 UTF-8）
    output.write('﻿')
    writer = csv.writer(output)
    writer.writerow(['所属模块', '用例标题', '前置条件', '用例类型', '优先级', '步骤', '预期'])
    for row in rows:
        writer.writerow([
            row.get('module', ''),
            row.get('title', ''),
            row.get('precondition', ''),
            row.get('case_type', ''),
            row.get('priority', ''),
            row.get('step', ''),
            row.get('expected', ''),
        ])
    return output.getvalue().encode('utf-8-sig')


# ====== Excel 导出 ======

def generate_xlsx(rows: List[Dict[str, Any]]) -> bytes:
    """生成 .xlsx 文件字节，支持单元格合并"""
    wb = Workbook()
    ws = wb.active
    ws.title = '测试用例'

    # 样式定义
    header_font = Font(bold=True, size=11)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )
    center_align = Alignment(horizontal='center', vertical='center')
    wrap_align = Alignment(vertical='center', wrap_text=True)

    headers = ['所属模块', '用例标题', '前置条件', '用例类型', '优先级', '步骤', '预期']

    # 写入表头
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = center_align

    # 写入数据行
    for i, row in enumerate(rows, 2):
        values = [
            row.get('module', ''),
            row.get('title', ''),
            row.get('precondition', ''),
            row.get('case_type', ''),
            row.get('priority', ''),
            row.get('step', ''),
            row.get('expected', ''),
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=i, column=col, value=val)
            cell.border = thin_border
            cell.alignment = wrap_align

    # 合并单元格：同一用例标题下的前5列（所属模块、用例标题、前置条件、用例类型、P）
    if rows:
        merge_start_row = 2
        current_title = rows[0].get('title', '')

        for i, row in enumerate(rows[1:], 3):  # 从第3行开始比较（第2行是第一条数据）
            row_title = row.get('title', '')
            if row_title != current_title:
                # 合并前一组
                if i - 1 > merge_start_row:
                    for col in range(1, 6):  # 列1-5
                        ws.merge_cells(
                            start_row=merge_start_row, start_column=col,
                            end_row=i - 1, end_column=col
                        )
                merge_start_row = i
                current_title = row_title

        # 处理最后一组
        total_rows = len(rows) + 1  # +1 因为数据从第2行开始
        if total_rows > merge_start_row:
            for col in range(1, 6):
                ws.merge_cells(
                    start_row=merge_start_row, start_column=col,
                    end_row=total_rows, end_column=col
                )

    # 调整列宽
    column_widths = [16, 30, 24, 12, 8, 50, 50]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # 所有合并后的单元格居中
    for row in ws.iter_rows(min_row=1, max_row=len(rows) + 1, min_col=1, max_col=7):
        for cell in row:
            if cell.row == 1:
                continue
            cell.alignment = wrap_align

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ====== 需求清单 → 列名映射 ======

# 需求清单 Excel 列名映射。
# 匹配规则：先精确全字匹配，再按关键词包含匹配。
_REQUIREMENT_COLUMN_KEYWORDS = {
    'module':       ['模块', '目录', '一级', 'module'],
    'title':        ['需求', '功能', '特性', '故事', 'title', 'feature', 'name', '项', '点'],
    'description':  ['描述', '说明', '备注', '内容', '详情', 'desc', 'remark', 'note'],
    'priority':     ['优先级', '优先', '重要', '级别', '等级', 'priority'],
    'req_type':     ['类型', '分类', 'type', '种类'],
}


def _normalize_requirement_column(raw: str) -> str | None:
    """将需求清单 Excel 表头映射为标准字段名。
    先用精确匹配、再用关键词包含匹配，最后尝试去标点再匹配。"""
    cleaned = raw.strip().lower().replace('\n', '').replace('\r', '').replace(' ', '')
    if not cleaned:
        return None

    # 第一轮：精确全字匹配
    exact_map = {
        'module':       ['所属模块', '功能模块', '需求模块', '一级模块', '二级模块', '模块名称',
                        '模块', '一级目录', '二级目录', '目录', '系统', '子系统', 'module', 'mod'],
        'title':        ['需求名称', '功能名称', '需求标题', '功能标题', '功能点', '需求项', '功能项',
                        '需求点', '特性', 'feature', 'userstory', 'story', 'name'],
        'description':  ['需求描述', '功能说明', '需求内容', '需求详情', '详细描述', '具体描述',
                        '描述', '说明', '备注', '内容', 'desc', 'remark', 'description', 'note'],
        'priority':     ['优先级', '优先', '重要程度', '重要性', '等级', '级别', 'priority', 'level'],
        'req_type':     ['需求类型', '功能类型', '类型', '分类', 'type', 'req_type', 'category'],
    }
    for field, aliases in exact_map.items():
        if cleaned in [a.lower().replace(' ', '') for a in aliases]:
            return field

    # 第二轮：关键词包含匹配（如「一级功能模块」包含「模块」→ module）
    keyword_priority = ['module', 'title', 'description', 'priority', 'req_type']
    for field in keyword_priority:
        for kw in _REQUIREMENT_COLUMN_KEYWORDS.get(field, []):
            if kw and kw.lower() in cleaned:
                return field

    return None


def parse_excel_to_rows(file_content: bytes) -> tuple[list[dict], list[str]]:
    """
    解析需求清单 Excel，返回 (rows, warnings)。
    自动识别表头列名，至少需要「模块」「需求名称」两列。
    需求清单与测试用例清单不同：需求只有模块+需求名+描述+优先级，没有步骤和预期。
    """
    from openpyxl import load_workbook

    # read_only=False 才能正确读取合并单元格的值
    wb = load_workbook(io.BytesIO(file_content), read_only=False, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("Excel 文件中没有可用的工作表")

    rows_iter = list(ws.iter_rows(values_only=True))
    if len(rows_iter) < 2:
        raise ValueError("Excel 文件至少需要包含表头和 1 行数据")

    # --- 解析表头 ---
    header_row = rows_iter[0]
    col_map: dict[int, str] = {}
    warnings: list[str] = []

    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        raw = str(cell).strip()
        field = _normalize_requirement_column(raw)
        if field:
            if field in col_map.values():
                warnings.append(f"列「{raw}」映射到 {field}，但该字段已被其他列映射，将跳过")
            else:
                col_map[idx] = field

    required = {'module', 'title'}
    missing = required - set(col_map.values())
    if missing:
        raise ValueError(
            f"缺少必要列：{', '.join(missing)}。"
            f"已识别的列：{', '.join(col_map.values()) if col_map else '无'}。"
            f"需求清单 Excel 至少需要：「模块/所属模块」「需求名称/功能名称」两列"
        )

    # --- 解析数据行 ---
    rows: list[dict] = []
    last_module = ''  # 合并单元格/向下填充

    for row_idx, row in enumerate(rows_iter[1:], 2):
        record = {
            'module': '',
            'title': '',
            'description': '',
            'priority': '',
            'req_type': '功能需求',
        }
        for col_idx, field in col_map.items():
            val = row[col_idx] if col_idx < len(row) else None
            record[field] = str(val).strip() if val is not None else ''

        # 模块向下填充：如果当前行模块为空，沿用上一行的模块
        if not record['module'] and last_module:
            record['module'] = last_module
        if record['module']:
            last_module = record['module']

        # 跳过空行
        if not record['module'] and not record['title']:
            continue

        if not record['module']:
            warnings.append(f"第 {row_idx} 缺少「模块」，已跳过")
            continue
        if not record['title']:
            warnings.append(f"第 {row_idx} 缺少「需求名称」，已跳过")
            continue

        rows.append(record)

    if not rows:
        raise ValueError("Excel 文件中未解析到有效数据行，请检查内容")

    return rows, warnings


# ====== 示例 Excel 模板 ======

def generate_sample_excel() -> bytes:
    """生成需求清单示例 Excel，供用户参考格式"""
    wb = Workbook()
    ws = wb.active
    ws.title = '需求清单示例'

    # 表头
    headers = ['所属模块', '需求名称', '需求描述', '需求类型', '优先级']
    header_font = Font(bold=True, size=11, color='FFFFFF')
    header_fill = openpyxl_styles_PatternFill(start_color='1677ff', end_color='1677ff', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    wrap_align = Alignment(vertical='center', wrap_text=True)
    center_align = Alignment(horizontal='center', vertical='center')

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    # 示例数据（需求，不是用例）
    sample_data = [
        ['登录模块', '账号密码登录', '支持用户使用手机号/邮箱+密码登录', '功能需求', 'P1'],
        ['登录模块', '短信验证码登录', '支持手机号+短信验证码登录', '功能需求', 'P1'],
        ['登录模块', '第三方登录', '支持微信/支付宝OAuth授权登录', '功能需求', 'P2'],
        ['登录模块', '登录失败锁定', '连续5次失败后锁定30分钟', '安全需求', 'P1'],
        ['个人中心', '查看个人信息', '展示头像、昵称、手机号等基本信息', '功能需求', 'P1'],
        ['个人中心', '修改个人资料', '支持修改昵称、头像、性别、生日等', '功能需求', 'P1'],
        ['个人中心', '修改密码', '通过旧密码验证后设置新密码', '安全需求', 'P2'],
        ['个人中心', '账号注销', '用户可申请注销账号，30天冷静期', '功能需求', 'P3'],
    ]

    for i, row_data in enumerate(sample_data, 2):
        for j, val in enumerate(row_data, 1):
            cell = ws.cell(row=i, column=j, value=val)
            cell.border = thin_border
            cell.alignment = wrap_align

    # 列宽
    widths = [16, 28, 40, 14, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
