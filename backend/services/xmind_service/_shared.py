"""
XMind 转换服务 - 公共 import / 常量 / 小工具
供 parse / excel / generate 子模块共享，避免重复与循环依赖。
"""
import zipfile
import json
import csv
import io
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# 延迟导入解决 openpyxl.styles.PatternFill 命名冲突（以别名方式引入，避免污染命名空间）
from openpyxl.styles import PatternFill as openpyxl_styles_PatternFill
