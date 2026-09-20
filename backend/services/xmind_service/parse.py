"""
XMind 解析 - 解析 .xmind 文件并合并步骤
支持 XMind 8 (content.xml) 和 XMind 2020+ (content.json) 两种格式
"""
from ._shared import *  # noqa: F401,F403  （zipfile / json / io / ET / typing 等）

__all__ = ['parse_xmind']


# ====== XMind 解析 ======

def parse_xmind(file_content: bytes) -> List[Dict[str, Any]]:
    """
    解析 .xmind 文件，返回数据行列表（已合并同一用例的多个步骤）。
    每行包含：module, title, precondition, case_type, priority, step, expected
    """
    with zipfile.ZipFile(io.BytesIO(file_content)) as z:
        namelist = z.namelist()

        # 优先尝试 content.json（XMind 2020+）
        if 'content.json' in namelist:
            with z.open('content.json') as f:
                data = json.load(f)
            raw_rows = _parse_content_json(data)
            return _merge_steps(raw_rows)

        # 其次 content.xml（XMind 8）
        if 'content.xml' in namelist:
            with z.open('content.xml') as f:
                tree = ET.parse(f)
            raw_rows = _parse_content_xml(tree)
            return _merge_steps(raw_rows)

        raise ValueError("无法识别的 XMind 文件格式：未找到 content.json 或 content.xml")


# -------- JSON 格式解析（XMind 2020+）--------

def _parse_content_json(data: dict) -> List[Dict[str, Any]]:
    """解析 XMind 2020+ 的 content.json"""
    # 数据结构通常是 [{rootTopic: ...}] 或直接的 {rootTopic: ...}
    if isinstance(data, list):
        # 取第一个 sheet
        root_topic = data[0].get('rootTopic', {}) if data else {}
    else:
        root_topic = data.get('rootTopic', {})

    rows: List[Dict[str, Any]] = []
    _walk_json_topics(root_topic, rows, depth=0, context={})
    return rows


def _walk_json_topics(topic: dict, rows: List[Dict], depth: int, context: dict):
    """递归遍历 JSON 主题树"""
    title = (topic.get('title', '') or '').strip()

    if depth == 0:
        # 根节点：跳过，只处理子节点
        pass
    elif depth == 1:
        # 第1层 → 所属模块
        context['module'] = title
    elif depth == 2:
        # 第2层 → 用例标题（同时提取前置条件、用例类型、优先级）
        context['title'] = title

        # 提取 notes → 前置条件
        notes = topic.get('notes', {})
        if isinstance(notes, dict):
            plain = notes.get('plain', {})
            if isinstance(plain, dict):
                context['precondition'] = (plain.get('content') or '').strip()
            else:
                context['precondition'] = ''

        # 提取 labels → 用例类型
        labels = topic.get('labels', [])
        context['case_type'] = labels[0] if labels else '功能测试'

        # 提取 markers → 优先级 P
        markers = topic.get('markers', [])
        context['priority'] = _parse_json_marker_priority(markers)

        # 如果之前没有设置 precondition 和 case_type（可能在父级未设置），设置默认值
        context.setdefault('precondition', '')
        context.setdefault('case_type', '功能测试')
        context.setdefault('priority', '')
    elif depth == 3:
        # 第3层 → 步骤
        context['step'] = title
    elif depth == 4:
        # 第4层 → 预期结果，生成行记录
        rows.append({
            'module': context.get('module', ''),
            'title': context.get('title', ''),
            'precondition': context.get('precondition', ''),
            'case_type': context.get('case_type', '功能测试'),
            'priority': context.get('priority', ''),
            'step': context.get('step', ''),
            'expected': title,
        })
        return  # 不继续递归第4层的子节点

    # 继续递归子节点
    children = topic.get('children', {})
    if isinstance(children, dict):
        attached = children.get('attached', [])
    else:
        attached = []
    for child in attached:
        _walk_json_topics(child, rows, depth + 1, context.copy())


def _parse_json_marker_priority(markers: list) -> str:
    """JSON 格式：根据 markerId 提取优先级"""
    priority_map = {
        'priority-1': '1',
        'priority-2': '2',
        'priority-3': '3',
        'priority-4': '4',
    }
    for marker in markers:
        if isinstance(marker, dict):
            mid = marker.get('markerId', '')
            if mid in priority_map:
                return priority_map[mid]
    return ''


# -------- XML 格式解析（XMind 8）--------

def _parse_content_xml(tree: ET.ElementTree) -> List[Dict[str, Any]]:
    """解析 XMind 8 的 content.xml"""
    root = tree.getroot()
    ns = _detect_xml_namespace(root)

    # 尝试多种方式找到根 topic
    # XMind 8 的根元素通常是 <xmap-content>，其下有 <sheet> → <topic>
    if root.tag.endswith('xmap-content'):
        # 查找第一个 sheet
        sheet = root.find(f'{ns}sheet') if ns else root.find('sheet')
        if sheet is not None:
            topic_el = sheet.find(f'{ns}topic') if ns else sheet.find('topic')
        else:
            topic_el = root.find(f'.//{ns}topic') if ns else root.find('.//topic')
    else:
        # 可能是直接以 topic 为根
        topic_el = root

    if topic_el is None:
        return []

    rows: List[Dict[str, Any]] = []
    _walk_xml_topics(topic_el, rows, depth=0, context={}, ns=ns)
    return rows


def _detect_xml_namespace(root: ET.Element) -> str:
    """检测 XML 命名空间前缀"""
    tag = root.tag
    if '}' in tag:
        # 格式：{urn:xmind:xmap:xmlns:content:3.0}xmap-content
        return tag.split('}')[0] + '}'
    return ''


def _ns_tag(ns: str, name: str) -> str:
    """生成带命名空间的标签名"""
    return f'{ns}{name}' if ns else name


def _walk_xml_topics(topic_el: ET.Element, rows: List[Dict], depth: int, context: dict, ns: str):
    """递归遍历 XML 主题树"""

    def _find(tag):
        return topic_el.find(_ns_tag(ns, tag))

    def _findall(tag):
        return topic_el.findall(_ns_tag(ns, tag))

    title_el = _find('title')
    title = title_el.text.strip() if title_el is not None and title_el.text else ''

    if depth == 0:
        pass  # 根节点
    elif depth == 1:
        context['module'] = title
    elif depth == 2:
        context['title'] = title

        # notes → 前置条件
        notes_el = _find('notes')
        if notes_el is not None:
            plain_el = notes_el.find(_ns_tag(ns, 'plain'))
            context['precondition'] = plain_el.text.strip() if plain_el is not None and plain_el.text else ''
        else:
            context['precondition'] = ''

        # labels → 用例类型
        labels_el = _find('labels')
        if labels_el is not None:
            label_texts = []
            for lbl in labels_el.findall(_ns_tag(ns, 'label')):
                if lbl.text:
                    label_texts.append(lbl.text.strip())
            context['case_type'] = label_texts[0] if label_texts else '功能测试'
        else:
            context['case_type'] = '功能测试'

        # markers → 优先级
        context['priority'] = _parse_xml_marker_priority(topic_el, ns)

    elif depth == 3:
        context['step'] = title
    elif depth == 4:
        rows.append({
            'module': context.get('module', ''),
            'title': context.get('title', ''),
            'precondition': context.get('precondition', ''),
            'case_type': context.get('case_type', '功能测试'),
            'priority': context.get('priority', ''),
            'step': context.get('step', ''),
            'expected': title,
        })
        return

    # 寻找子节点
    children_el = _find('children')
    if children_el is not None:
        topics_el = children_el.find(_ns_tag(ns, 'topics'))
        if topics_el is not None:
            for child in topics_el.findall(_ns_tag(ns, 'topic')):
                _walk_xml_topics(child, rows, depth + 1, context.copy(), ns)


def _parse_xml_marker_priority(topic_el: ET.Element, ns: str) -> str:
    """XML 格式：提取 marker-ref 的优先级"""
    priority_map = {
        'priority-1': '1',
        'priority-2': '2',
        'priority-3': '3',
        'priority-4': '4',
    }
    for child in topic_el:
        tag = child.tag
        if ns and ns in tag:
            tag = tag.replace(ns, '')
        if tag == 'marker-refs':
            for mr in child.findall(_ns_tag(ns, 'marker-ref')):
                mid = mr.get('marker-id', '')
                if mid in priority_map:
                    return priority_map[mid]
    return ''


# ====== 步骤合并 ======

def _merge_steps(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将同一用例标题下的多个步骤合并为一行，步骤和预期结果编号换行拼接"""
    from collections import OrderedDict

    groups: OrderedDict = OrderedDict()

    for row in raw_rows:
        key = (row['module'], row['title'])
        if key not in groups:
            groups[key] = {
                'module': row['module'],
                'title': row['title'],
                'precondition': row['precondition'],
                'case_type': row['case_type'],
                'priority': row['priority'],
                'steps': OrderedDict(),  # step -> [expecteds]
            }
        step = row['step']
        if step not in groups[key]['steps']:
            groups[key]['steps'][step] = []
        groups[key]['steps'][step].append(row['expected'])

    merged = []
    for group in groups.values():
        step_lines = []
        expected_lines = []
        step_num = 1
        for step, expecteds in group['steps'].items():
            step_lines.append(f"{step_num}. {step}")
            for exp in expecteds:
                expected_lines.append(f"{step_num}. {exp}")
            step_num += 1

        merged.append({
            'module': group['module'],
            'title': group['title'],
            'precondition': group['precondition'],
            'case_type': group['case_type'],
            'priority': group['priority'],
            'step': '\n'.join(step_lines),
            'expected': '\n'.join(expected_lines),
        })

    return merged
