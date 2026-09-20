"""
XMind 转换服务 - 解析 XMind 文件并导出为 CSV/Excel，以及需求清单 → XMind
支持 XMind 8 (content.xml) 和 XMind 2020+ (content.json) 两种格式

本包由原单文件 services/xmind_service.py 拆分而来，__init__ 作为门面重导出所有
原有对外公共名称，保证 `from services.xmind_service import <名称>` 全部仍然可用。
"""
from .parse import *      # noqa: F401,F403  parse_xmind
from .excel import *      # noqa: F401,F403  generate_csv / generate_xlsx / parse_excel_to_rows / generate_sample_excel
from .generate import *   # noqa: F401,F403  generate_template / generate_xmind_bytes

__all__ = [
    'parse_xmind',
    'generate_csv',
    'generate_xlsx',
    'generate_template',
    'parse_excel_to_rows',
    'generate_xmind_bytes',
    'generate_sample_excel',
]
