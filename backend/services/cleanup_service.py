"""
Data cleanup service for removing soft-deleted records
"""
import re
import importlib
import pkgutil
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

PHYSICAL_CLEANUP_EXCLUDED_TABLES = set()

_CLEANUP_SENSITIVE_COLUMN_PARTS = (
    "password", "token", "secret", "api_key", "apikey", "authorization", "cookie",
    "header", "credential", "private", "request", "response", "body", "content",
    "script", "prompt", "phone", "email", "address", "url", "json", "detail",
    "remark",
)
_CLEANUP_SAFE_COLUMN_PARTS = (
    "name", "title", "code", "status", "type", "scope", "model", "module", "operation",
)
_CLEANUP_SAFE_COLUMN_NAMES = {
    "id", "created_at", "updated_at", "deleted_at", "user_id", "owner_id", "created_by",
    "updated_by", "project_id", "system_id", "environment_id", "model_id",
}


def _load_all_model_modules() -> None:
    """自动加载 models 包下的所有模型模块，让新表随模型代码自动进入元数据。"""
    models_package = importlib.import_module("models")
    for module_info in pkgutil.iter_modules(models_package.__path__, f"{models_package.__name__}."):
        importlib.import_module(module_info.name)


def _is_safe_cleanup_column(column_name: str) -> bool:
    normalized_name = column_name.lower()
    if normalized_name == "is_deleted":
        return False
    if any(part in normalized_name for part in _CLEANUP_SENSITIVE_COLUMN_PARTS):
        return False
    return normalized_name in _CLEANUP_SAFE_COLUMN_NAMES or any(
        part in normalized_name for part in _CLEANUP_SAFE_COLUMN_PARTS
    )


def _cleanup_column_label(column: Dict[str, object]) -> str:
    if column.get("name") == "id":
        return "记录编号"
    if column.get("chinese_name"):
        return str(column["chinese_name"])
    return "业务字段"


def build_cleanup_display_columns(table_metadata: Dict[str, object]) -> tuple[list[Dict[str, object]], list[Dict[str, str]]]:
    """构造清理详情的安全投影，不把原始字段名和敏感字段返回给前端。"""
    selected_columns = [
        column for column in table_metadata.get("columns", [])
        if _is_safe_cleanup_column(str(column.get("name", "")))
    ][:10]
    display_columns = [
        {"key": f"field_{index}", "label": _cleanup_column_label(column)}
        for index, column in enumerate(selected_columns)
    ]
    return selected_columns, display_columns


def _serialize_cleanup_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 200:
            return f"{value[:200]}…"
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return "[结构化内容]"


def build_cleanup_relation_display(relation: Dict[str, object]) -> Dict[str, object]:
    """返回清理详情需要的关联摘要，隐藏表名和字段名。"""
    return {
        "direction": relation.get("direction", ""),
        "related_chinese_name": relation.get("related_chinese_name", "") or "关联表",
        "related_count": relation.get("related_count", 0),
        "action": relation.get("action", ""),
    }


def get_model_cleanup_tables() -> Dict[str, Dict[str, object]]:
    """返回当前模型注册表中具备标准软删除字段的表及其中文元数据。"""
    from db.session import Base

    _load_all_model_modules()

    tables: Dict[str, Dict[str, object]] = {}
    for table in Base.metadata.sorted_tables:
        if "is_deleted" not in table.c or "deleted_at" not in table.c:
            continue
        tables[table.name] = {
            "table_name": table.name,
            "chinese_name": table.comment or "",
            "columns": [
                {
                    "name": column.name,
                    "chinese_name": column.comment or "",
                }
                for column in table.columns
            ],
        }
    return tables


async def _get_relation_rows(db: AsyncSession, table_name: str | None = None):
    from core.config import settings

    table_condition = ""
    params = {"db_name": settings.DATABASE_NAME}
    if table_name:
        table_condition = "AND (k.TABLE_NAME = :table_name OR k.REFERENCED_TABLE_NAME = :table_name)"
        params["table_name"] = table_name
    result = await db.execute(
        text(
            f"""
            SELECT
                k.TABLE_NAME,
                k.COLUMN_NAME,
                k.REFERENCED_TABLE_NAME,
                k.REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
            WHERE k.TABLE_SCHEMA = :db_name
              AND k.REFERENCED_TABLE_NAME IS NOT NULL
              {table_condition}
            ORDER BY k.TABLE_NAME, k.COLUMN_NAME
            """
        ),
        params,
    )
    return result.fetchall()


def _format_relation_row(
    row,
    table_name: str,
    table_metadata: Dict[str, Dict[str, object]],
) -> Dict[str, object]:
    child_table, child_column, parent_table, parent_column = row
    is_parent = parent_table == table_name
    related_table = child_table if is_parent else parent_table
    related_metadata = table_metadata.get(related_table, {})
    local_column = parent_column if is_parent else child_column
    related_column = child_column if is_parent else parent_column
    related_is_soft = "is_deleted" in {
        column["name"] for column in related_metadata.get("columns", [])
    }
    if is_parent:
        action = "优先清理子表" if related_is_soft else "可级联删除子数据"
    else:
        action = "受父表关联，父表保留"
    return {
        "direction": "被引用" if is_parent else "引用",
        "related_table": related_table,
        "related_chinese_name": related_metadata.get("chinese_name", ""),
        "source_column": local_column,
        "related_column": related_column,
        "relation_type": "子表" if is_parent else "父表",
        "action": action,
        "related_count": 0,
    }


async def get_all_table_relations(db: AsyncSession) -> Dict[str, List[Dict[str, object]]]:
    """一次读取当前模型表的全部外键关系。"""
    table_metadata = get_model_cleanup_tables()
    relations = {name: [] for name in table_metadata}
    for row in await _get_relation_rows(db):
        child_table, _, parent_table, _ = row
        if child_table in relations:
            relations[child_table].append(_format_relation_row(row, child_table, table_metadata))
        if parent_table in relations and parent_table != child_table:
            relations[parent_table].append(_format_relation_row(row, parent_table, table_metadata))
    return relations


async def get_table_relations(
    db: AsyncSession,
    table_name: str,
    cutoff_time: datetime | None = None,
) -> List[Dict[str, object]]:
    """读取指定表的外键关系，并统计当前截止时间下的关联影响数量。"""
    table_metadata = get_model_cleanup_tables()
    relations = [
        _format_relation_row(row, table_name, table_metadata)
        for row in await _get_relation_rows(db, table_name)
    ]
    if cutoff_time is None:
        return relations

    for relation in relations:
        related_table = relation["related_table"]
        if relation["relation_type"] == "子表":
            sql = f"""
                SELECT COUNT(*)
                FROM `{related_table}` AS related_row
                JOIN `{table_name}` AS target_row
                  ON related_row.`{relation['related_column']}` = target_row.`{relation['source_column']}`
                WHERE target_row.is_deleted = 1
                  AND target_row.deleted_at IS NOT NULL
                  AND target_row.deleted_at <= :cutoff_time
            """
        else:
            sql = f"""
                SELECT COUNT(*)
                FROM `{table_name}` AS target_row
                JOIN `{related_table}` AS related_row
                  ON target_row.`{relation['source_column']}` = related_row.`{relation['related_column']}`
                WHERE target_row.is_deleted = 1
                  AND target_row.deleted_at IS NOT NULL
                  AND target_row.deleted_at <= :cutoff_time
            """
        result = await db.execute(text(sql), {"cutoff_time": cutoff_time})
        relation["related_count"] = result.scalar() or 0
    return relations


def parse_db_error(error: Exception) -> str:
    """解析数据库错误，返回用户友好的提示"""
    error_str = str(error)
    
    # 外键约束错误 (MySQL Error 1451)
    if "foreign key constraint" in error_str.lower() or "1451" in error_str:
        match = re.search(r'CONSTRAINT `?([^`\s]+)`?.*REFERENCES `?([^`\s]+)`?', error_str, re.IGNORECASE)
        if match:
            fk_name = match.group(1)
            ref_table = match.group(2)
            return f"外键约束冲突：该表被表 `{ref_table}` 通过外键 `{fk_name}` 引用。请先清理引用表的数据。"
        return "外键约束冲突：存在其他表引用此表的数据，无法直接删除。请检查数据依赖关系。"
    
    return "数据库操作失败，请查看系统日志获取详情。"


async def get_pending_cleanup_data(
    db: AsyncSession,
    table_name: str,
    cutoff_time: datetime
) -> Dict[str, any]:
    """
    获取指定表的待清理数据
    
    Args:
        db: 数据库会话
        table_name: 表名
        cutoff_time: 截止时间
        
    Returns:
        待清理数据统计和样本数据
    """
    try:
        table_metadata = get_model_cleanup_tables().get(table_name, {})
        selected_columns, display_columns = build_cleanup_display_columns(table_metadata)
        # 统计数量：is_deleted=1 AND deleted_at有值 AND deleted_at <= cutoff_time
        count_sql = f"""
            SELECT COUNT(*) FROM `{table_name}` 
            WHERE is_deleted = 1 
            AND deleted_at IS NOT NULL
            AND deleted_at <= :cutoff_time
        """

        # 统计数量
        count_result = await db.execute(text(count_sql), {"cutoff_time": cutoff_time})
        total_count = count_result.scalar() or 0

        sample_data = []
        if selected_columns:
            column_names = [column["name"] for column in selected_columns]
            quoted_columns = ", ".join(f"`{column_name}`" for column_name in column_names)
            sample_sql = f"""
                SELECT {quoted_columns} FROM `{table_name}`
                WHERE is_deleted = 1
                AND deleted_at IS NOT NULL
                AND deleted_at <= :cutoff_time
                LIMIT 100
            """
            sample_result = await db.execute(text(sample_sql), {"cutoff_time": cutoff_time})
            rows = sample_result.fetchall()

            # 只按无业务含义的显示键返回，避免暴露字段名和原始敏感值。
            for row in rows:
                row_values = {
                    column["name"]: _serialize_cleanup_value(row[index])
                    for index, column in enumerate(selected_columns)
                }
                sample_data.append({
                    display_column["key"]: row_values[column["name"]]
                    for column, display_column in zip(selected_columns, display_columns)
                })

        return {
            "success": True,
            "table_name": table_name,
            "total_count": total_count,
            "cutoff_time": cutoff_time.isoformat(),
            "sample_data": sample_data,
            "display_columns": display_columns,
        }
        
    except Exception as e:
        logger.error(f"Failed to get pending data for table {table_name}: {str(e)}")
        return {
            "success": False,
            "table_name": table_name,
            "error": str(e),
            "total_count": 0,
            "sample_data": [],
            "display_columns": [],
        }


async def get_table_dependencies(db: AsyncSession, db_name: str) -> Dict[str, List[str]]:
    """
    获取表之间的外键依赖关系
    
    Args:
        db: 数据库会话
        db_name: 数据库名
        
    Returns:
        依赖关系字典，key为表名，value为该表依赖的父表列表
        例如：{'api_interface_collections': ['api_interface_collections'], 'users': []}
    """
    query = f"""
        SELECT 
            TABLE_NAME,
            REFERENCED_TABLE_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{db_name}'
        AND REFERENCED_TABLE_NAME IS NOT NULL
        AND REFERENCED_TABLE_NAME IN (
            SELECT DISTINCT TABLE_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = '{db_name}'
            AND COLUMN_NAME = 'is_deleted'
        )
    """
    result = await db.execute(text(query))
    rows = result.fetchall()
    
    # 构建依赖关系
    dependencies = {}
    for table_name, referenced_table in rows:
        if table_name not in dependencies:
            dependencies[table_name] = []
        if referenced_table not in dependencies[table_name]:
            dependencies[table_name].append(referenced_table)
    
    return dependencies


async def get_incoming_foreign_keys(db: AsyncSession, db_name: str, parent_tables: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """获取指向待清理表的外键关系，用于跳过仍被引用的父表记录"""
    if not parent_tables:
        return {}

    table_params = {f"table_{index}": table for index, table in enumerate(parent_tables)}
    placeholders = ", ".join(f":{key}" for key in table_params)
    query = f"""
        SELECT
            k.TABLE_NAME,
            k.COLUMN_NAME,
            k.REFERENCED_TABLE_NAME,
            k.REFERENCED_COLUMN_NAME,
            MAX(CASE WHEN c.COLUMN_NAME = 'is_deleted' THEN 1 ELSE 0 END) AS has_is_deleted,
            MAX(CASE WHEN c.COLUMN_NAME = 'deleted_at' THEN 1 ELSE 0 END) AS has_deleted_at
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
        LEFT JOIN INFORMATION_SCHEMA.COLUMNS c
            ON c.TABLE_SCHEMA = k.TABLE_SCHEMA
            AND c.TABLE_NAME = k.TABLE_NAME
        WHERE k.TABLE_SCHEMA = :db_name
        AND k.REFERENCED_TABLE_NAME IN ({placeholders})
        AND k.REFERENCED_TABLE_NAME IS NOT NULL
        GROUP BY k.TABLE_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME
    """
    result = await db.execute(text(query), {"db_name": db_name, **table_params})
    rows = result.fetchall()

    incoming = {table: [] for table in parent_tables}
    for child_table, child_column, parent_table, parent_column, has_is_deleted, has_deleted_at in rows:
        incoming.setdefault(parent_table, []).append({
            "child_table": child_table,
            "child_column": child_column,
            "parent_column": parent_column,
            "is_soft_delete_table": bool(has_is_deleted and has_deleted_at),
        })

    return incoming


def build_child_cleanup_sql(parent_table: str, child_table: str, child_column: str, parent_column: str) -> str:
    """构造硬关联子表清理 SQL：删除指向待清理父记录的子表数据"""
    return f"""
                    DELETE child FROM `{child_table}` AS child
                    JOIN `{parent_table}` AS parent_target
                        ON child.`{child_column}` = parent_target.`{parent_column}`
                    WHERE parent_target.is_deleted = 1
                    AND parent_target.deleted_at IS NOT NULL
                    AND parent_target.deleted_at <= :cutoff_time
                """


def build_safe_delete_sql(table_name: str, incoming_relations: List[Dict[str, str]]) -> str:
    """构造安全删除 SQL：只删除未被其他表引用的软删除记录"""
    joins = []
    conditions = [
        "target.is_deleted = 1",
        "target.deleted_at IS NOT NULL",
        "target.deleted_at <= :cutoff_time",
    ]

    for index, relation in enumerate(incoming_relations):
        child_table = relation["child_table"]
        child_column = relation["child_column"]
        parent_column = relation["parent_column"]
        child_alias = f"child_{index}"
        joins.append(
            f"LEFT JOIN `{child_table}` AS {child_alias} "
            f"ON {child_alias}.`{child_column}` = target.`{parent_column}`"
        )
        conditions.append(f"{child_alias}.`{child_column}` IS NULL")

    where_clause = "\n                    AND ".join(conditions)
    join_clause = "\n                    ".join(joins)
    join_clause = f"\n                    {join_clause}" if join_clause else ""
    return f"""
                    DELETE target FROM `{table_name}` AS target{join_clause}
                    WHERE {where_clause}
                """


def split_child_relations(incoming_relations: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """拆分软删除子表和硬删除子表关系"""
    soft_relations = []
    hard_relations = []
    for relation in incoming_relations:
        if relation.get("is_soft_delete_table"):
            soft_relations.append(relation)
        else:
            hard_relations.append(relation)
    return soft_relations, hard_relations


def build_pending_count_sql(table_name: str) -> str:
    """构造待清理数据统计 SQL"""
    return f"""
                    SELECT COUNT(*) FROM `{table_name}`
                    WHERE is_deleted = 1
                    AND deleted_at IS NOT NULL
                    AND deleted_at <= :cutoff_time
                """


def format_related_delete_summary(related_deleted_counts: Dict[str, int]) -> str:
    """格式化关联表清理结果说明"""
    if not related_deleted_counts:
        return ""

    total_related_deleted = sum(related_deleted_counts.values())
    return f"，并清理 {total_related_deleted} 条关联数据"


def topological_sort(tables: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
    """
    拓扑排序，确定删除顺序（先删子表，后删父表）
    
    Args:
        tables: 所有需要清理的表
        dependencies: 依赖关系字典
        
    Returns:
        排序后的表列表，按删除顺序排列
    """
    # 删除顺序需要先删子表，再删父表。
    # dependencies 表示 table -> parent_tables，因此排序边应为 table -> parent。
    table_set = set(tables)
    in_degree = {table: 0 for table in tables}
    children_by_parent = {table: [] for table in tables}

    for table in tables:
        for parent in dependencies.get(table, []):
            if parent in table_set and parent != table:
                in_degree[parent] += 1
                children_by_parent[table].append(parent)

    queue = [table for table in tables if in_degree[table] == 0]
    result = []
    
    while queue:
        table = queue.pop(0)
        result.append(table)
        
        for parent in children_by_parent.get(table, []):
            in_degree[parent] -= 1
            if in_degree[parent] == 0:
                queue.append(parent)
    
    # 如果有循环依赖，将剩余表添加到结果中
    remaining = [t for t in tables if t not in result]
    result.extend(remaining)
    
    return result


async def cleanup_soft_deleted_data(
    db: AsyncSession,
    cutoff_time: datetime
) -> Dict[str, any]:
    """
    清理所有表的软删除数据
    
    Args:
        db: 数据库会话
        cutoff_time: 截止时间，清理 deleted_at <= cutoff_time 的数据
        
    Returns:
        清理结果统计
    """
    from core.config import settings
    db_name = settings.DATABASE_NAME
    
    # 只处理当前模型表，避免把历史遗留物理表带入清理范围。
    tables = [
        table_name
        for table_name in get_model_cleanup_tables()
        if table_name not in PHYSICAL_CLEANUP_EXCLUDED_TABLES
    ]
    
    if not tables:
        return {
            "success": True,
            "message": "没有找到需要清理的表",
            "tables_cleaned": 0,
            "total_records_deleted": 0,
            "details": [],
            "needs_more_cleanup": False
        }
    
    # 获取表之间的依赖关系并排序（先删子表，后删父表）
    dependencies = await get_table_dependencies(db, db_name)
    incoming_foreign_keys = await get_incoming_foreign_keys(db, db_name, tables)
    sorted_tables = topological_sort(tables, dependencies)
    
    logger.info(f"表删除顺序: {sorted_tables}")
    logger.info(f"依赖关系: {dependencies}")
    
    total_deleted = 0
    details = []
    tables_cleaned_set = set()
    max_passes = 5  # 最多执行 5 轮清理，防止死循环
    pass_count = 0
    
    # 循环清理直到没有数据被删除或达到最大轮次
    while pass_count < max_passes:
        pass_count += 1
        pass_deleted = 0
        logger.info(f"开始第 {pass_count} 轮清理...")
        
        # 按排序后的顺序删除
        for table_name in sorted_tables:
            try:
                related_deleted_counts = await cleanup_related_hard_delete_rows(
                    db=db,
                    parent_table=table_name,
                    incoming_relations=incoming_foreign_keys.get(table_name, []),
                    cutoff_time=cutoff_time,
                )
                for child_table, child_deleted_count in related_deleted_counts.items():
                    pass_deleted += child_deleted_count
                    total_deleted += child_deleted_count
                    tables_cleaned_set.add(child_table)
                    existing_detail = next((d for d in details if d["table"] == child_table), None)
                    if existing_detail:
                        existing_detail["records_deleted"] += child_deleted_count
                    else:
                        details.append({
                            "table": child_table,
                            "records_deleted": child_deleted_count,
                            "cutoff_time": cutoff_time.isoformat()
                        })

                soft_relations, _ = split_child_relations(incoming_foreign_keys.get(table_name, []))
                delete_sql = build_safe_delete_sql(
                    table_name,
                    soft_relations,
                )
                
                # 直接执行删除，通过 ROW_COUNT() 获取删除的记录数
                result = await db.execute(text(delete_sql), {"cutoff_time": cutoff_time})
                record_count = result.rowcount or 0
                
                if record_count > 0:
                    pass_deleted += record_count
                    total_deleted += record_count
                    tables_cleaned_set.add(table_name)
                    
                    # 更新或添加详情
                    existing_detail = next((d for d in details if d["table"] == table_name), None)
                    if existing_detail:
                        existing_detail["records_deleted"] += record_count
                    else:
                        details.append({
                            "table": table_name,
                            "records_deleted": record_count,
                            "cutoff_time": cutoff_time.isoformat()
                        })
                    
                    logger.info(f"第{pass_count}轮：从表 {table_name} 清理了 {record_count} 条记录")
                
            except Exception as e:
                friendly_msg = parse_db_error(e)
                logger.error(f"Failed to clean table {table_name}: {str(e)}")
                details.append({
                    "table": table_name,
                    "error": friendly_msg,
                    "records_deleted": 0
                })
        
        # 提交当前轮次的事务
        await db.commit()
        
        logger.info(f"第 {pass_count} 轮清理完成，本轮清理了 {pass_deleted} 条记录")
        
        # 如果本轮没有删除任何数据，说明已经清理完毕
        if pass_deleted == 0:
            logger.info("没有更多数据需要清理，退出循环")
            break
    
    remaining_total = 0
    for table_name in sorted_tables:
        count_result = await db.execute(
            text(build_pending_count_sql(table_name)),
            {"cutoff_time": cutoff_time},
        )
        remaining_count = count_result.scalar() or 0
        if remaining_count <= 0:
            continue

        remaining_total += remaining_count
        existing_detail = next((d for d in details if d["table"] == table_name), None)
        if existing_detail:
            existing_detail["remaining_count"] = remaining_count
        else:
            details.append({
                "table": table_name,
                "records_deleted": 0,
                "remaining_count": remaining_count,
            })

    # 判断是否还需要继续清理
    needs_more_cleanup = remaining_total > 0
    
    # 构建消息
    message = f"已清理 {len(tables_cleaned_set)} 个表中的 {total_deleted} 条数据"
    if remaining_total > 0:
        message += f"（仍有 {remaining_total} 条数据被关联数据引用，已自动跳过）"
    
    return {
        "success": True,
        "message": message,
        "tables_cleaned": len(tables_cleaned_set),
        "total_records_deleted": total_deleted,
        "cutoff_time": cutoff_time.isoformat(),
        "details": details,
        "remaining_records": remaining_total,
        "needs_more_cleanup": needs_more_cleanup
    }


async def cleanup_related_hard_delete_rows(
    db: AsyncSession,
    parent_table: str,
    incoming_relations: List[Dict[str, str]],
    cutoff_time: datetime,
) -> Dict[str, int]:
    """先清理不带软删除标记的关联子表数据，避免父表删除被外键阻塞"""
    deleted_counts: Dict[str, int] = {}
    _, hard_relations = split_child_relations(incoming_relations)

    for relation in hard_relations:
        delete_sql = build_child_cleanup_sql(
            parent_table=parent_table,
            child_table=relation["child_table"],
            child_column=relation["child_column"],
            parent_column=relation["parent_column"],
        )
        result = await db.execute(text(delete_sql), {"cutoff_time": cutoff_time})
        record_count = result.rowcount or 0
        if record_count > 0:
            deleted_counts[relation["child_table"]] = deleted_counts.get(relation["child_table"], 0) + record_count

    return deleted_counts


async def cleanup_single_table_data(
    db: AsyncSession,
    table_name: str,
    cutoff_time: datetime
) -> Dict[str, any]:
    """
    清理单个表的软删除数据（优化版：合并统计和删除）
    
    Args:
        db: 数据库会话
        table_name: 表名
        cutoff_time: 截止时间
        
    Returns:
        清理结果
    """
    if table_name in PHYSICAL_CLEANUP_EXCLUDED_TABLES:
        return {
            "success": False,
            "table_name": table_name,
            "records_deleted": 0,
            "message": f"Table {table_name} is excluded from physical cleanup",
        }

    try:
        from core.config import settings
        db_name = settings.DATABASE_NAME

        incoming_foreign_keys = await get_incoming_foreign_keys(db, db_name, [table_name])
        related_deleted_counts = await cleanup_related_hard_delete_rows(
            db=db,
            parent_table=table_name,
            incoming_relations=incoming_foreign_keys.get(table_name, []),
            cutoff_time=cutoff_time,
        )
        soft_relations, _ = split_child_relations(incoming_foreign_keys.get(table_name, []))
        delete_sql = build_safe_delete_sql(
            table_name,
            soft_relations,
        )
        
        result = await db.execute(text(delete_sql), {"cutoff_time": cutoff_time})
        record_count = result.rowcount or 0
        
        # 提交事务
        await db.commit()

        count_result = await db.execute(
            text(build_pending_count_sql(table_name)),
            {"cutoff_time": cutoff_time},
        )
        remaining_count = count_result.scalar() or 0
        
        if record_count > 0:
            logger.info(f"Cleaned {record_count} records from table {table_name}")
            
            return {
                "success": True,
                "table_name": table_name,
                "records_deleted": record_count,
                "remaining_count": remaining_count,
                "related_records_deleted": related_deleted_counts,
                "cutoff_time": cutoff_time.isoformat(),
                "message": f"成功从表 {table_name} 清理 {record_count} 条数据{format_related_delete_summary(related_deleted_counts)}"
            }
        elif remaining_count > 0:
            return {
                "success": True,
                "table_name": table_name,
                "records_deleted": 0,
                "remaining_count": remaining_count,
                "related_records_deleted": related_deleted_counts,
                "cutoff_time": cutoff_time.isoformat(),
                "message": f"表 {table_name} 仍有 {remaining_count} 条数据被关联数据引用，已自动跳过{format_related_delete_summary(related_deleted_counts)}"
            }
        else:
            return {
                "success": True,
                "table_name": table_name,
                "records_deleted": 0,
                "remaining_count": 0,
                "related_records_deleted": related_deleted_counts,
                "cutoff_time": cutoff_time.isoformat(),
                "message": f"表 {table_name} 没有需要清理的数据{format_related_delete_summary(related_deleted_counts)}"
            }
    
    except Exception as e:
        await db.rollback()  # 失败时回滚
        friendly_msg = parse_db_error(e)
        logger.error(f"Failed to clean table {table_name}: {str(e)}")
        return {
            "success": False,
            "table_name": table_name,
            "error": friendly_msg,  # 使用友好的错误消息
            "records_deleted": 0
        }
