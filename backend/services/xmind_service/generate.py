"""
XMind 生成 - 生成示例 XMind 模板，以及将需求清单行数据生成 XMind 文件
"""
from ._shared import *  # noqa: F401,F403  （zipfile / json / io 等）

__all__ = [
    'generate_template',
    'generate_xmind_bytes',
]


# ====== 模板生成 ======

def generate_template() -> bytes:
    """生成一个示例 XMind 模板文件（XMind 2020+ 格式），展示正确的4层结构"""
    import time as _time

    timestamp = int(_time.time() * 1000)

    manifest = {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        }
    }

    content = [{
        "id": "sheet1",
        "class": "sheet",
        "title": "Sheet 1",
        "rootTopic": {
            "id": "root",
            "class": "topic",
            "title": "测试用例模板",
            "children": {
                "attached": [
                    {
                        "id": "mod1",
                        "class": "topic",
                        "title": "登录模块",
                        "children": {
                            "attached": [
                                {
                                    "id": "case1",
                                    "class": "topic",
                                    "title": "用户登录-正常流程",
                                    "notes": {
                                        "plain": {
                                            "content": "用户已注册且账号状态正常"
                                        }
                                    },
                                    "labels": ["功能测试"],
                                    "markers": [
                                        {"markerId": "priority-1"}
                                    ],
                                    "children": {
                                        "attached": [
                                            {
                                                "id": "step1",
                                                "class": "topic",
                                                "title": "输入正确的用户名和密码，点击登录按钮",
                                                "children": {
                                                    "attached": [
                                                        {"id": "exp1a", "class": "topic", "title": "登录成功，页面跳转到首页"},
                                                        {"id": "exp1b", "class": "topic", "title": "顶部导航栏显示用户信息"},
                                                    ]
                                                }
                                            },
                                            {
                                                "id": "step2",
                                                "class": "topic",
                                                "title": "输入正确用户名和错误的密码，点击登录按钮",
                                                "children": {
                                                    "attached": [
                                                        {"id": "exp2", "class": "topic", "title": "提示【密码错误】，留在登录页面"},
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                },
                                {
                                    "id": "case2",
                                    "class": "topic",
                                    "title": "用户登录-异常流程",
                                    "labels": ["异常测试"],
                                    "markers": [
                                        {"markerId": "priority-2"}
                                    ],
                                    "children": {
                                        "attached": [
                                            {
                                                "id": "step3",
                                                "class": "topic",
                                                "title": "不输入用户名，直接点击登录按钮",
                                                "children": {
                                                    "attached": [
                                                        {"id": "exp3", "class": "topic", "title": "提示【请输入用户名】"},
                                                    ]
                                                }
                                            },
                                            {
                                                "id": "step4",
                                                "class": "topic",
                                                "title": "不输入密码，只输入用户名点击登录",
                                                "children": {
                                                    "attached": [
                                                        {"id": "exp4", "class": "topic", "title": "提示【请输入密码】"},
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "id": "mod2",
                        "class": "topic",
                        "title": "个人中心模块",
                        "children": {
                            "attached": [
                                {
                                    "id": "case3",
                                    "class": "topic",
                                    "title": "修改个人资料-成功",
                                    "notes": {
                                        "plain": {
                                            "content": "用户已登录"
                                        }
                                    },
                                    "labels": ["功能测试"],
                                    "markers": [
                                        {"markerId": "priority-1"}
                                    ],
                                    "children": {
                                        "attached": [
                                            {
                                                "id": "step5",
                                                "class": "topic",
                                                "title": "进入个人中心，修改昵称并保存",
                                                "children": {
                                                    "attached": [
                                                        {"id": "exp5", "class": "topic", "title": "提示【修改成功】，昵称更新为新值"},
                                                    ]
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }]

    metadata = {
        "creator": {
            "name": "智测平台",
            "version": "1.0",
        },
        "created": timestamp,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('content.json', json.dumps(content, ensure_ascii=False, indent=2))
        z.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2))
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue()


# ====== 需求清单 → XMind ======

def generate_xmind_bytes(rows: list[dict], root_title: str = "需求清单") -> bytes:
    """
    将需求清单行数据生成 XMind 文件（XMind 2020+ 格式，4 层结构）。
    第1层 → 模块
    第2层 → 需求名称（notes=需求描述，markers=优先级）
    第3层 → 占位节点「[步骤] 请在此填写测试步骤」
    第4层 → 占位节点「[预期] 请在此填写预期结果」

    用户在 XMind 中补充步骤/预期后，即可用「Xmind转用例」导出测试用例。
    """
    import time as _time

    def _make_topic(title: str, topic_id: str = ""):
        return {"id": topic_id, "class": "topic", "title": title}

    # 按 module 分组
    from collections import OrderedDict as _OD
    modules: _OD = _OD()
    for row in rows:
        mod = row['module']
        if mod not in modules:
            modules[mod] = []
        modules[mod].append({
            'title': row['title'],
            'description': row.get('description', ''),
            'priority': row.get('priority', ''),
            'req_type': row.get('req_type', ''),
        })

    # 构建 XMind（使用与 generate_template 完全一致的 ID 风格和结构）
    mod_idx = req_idx = step_idx = exp_idx = 0

    root = _make_topic(root_title, "root")
    root_children: list[dict] = []

    for mod_name, reqs in modules.items():
        mod_idx += 1
        mod_topic = _make_topic(mod_name, f"m{mod_idx}")
        mod_children: list[dict] = []

        for req in reqs:
            req_idx += 1
            step_idx += 1
            exp_idx += 1

            req_topic = _make_topic(req['title'], f"r{req_idx}")

            # notes → 需求描述
            desc = req['description']
            if desc:
                req_topic['notes'] = {"plain": {"content": desc}}

            # labels → 需求类型
            rtype = req['req_type']
            if rtype:
                req_topic['labels'] = [rtype]

            # markers → 优先级
            priority = req['priority']
            if priority:
                p_val = str(priority).upper().replace('P', '').strip()
                if p_val.isdigit() and 1 <= int(p_val) <= 4:
                    req_topic['markers'] = [{"markerId": f"priority-{p_val}"}]

            # 占位步骤和预期（供用户后续在 XMind 中填写）
            placeholder_step = _make_topic("[步骤] 请在此填写测试步骤", f"s{step_idx}")
            placeholder_exp = _make_topic("[预期] 请在此填写预期结果", f"e{exp_idx}")
            placeholder_step['children'] = {"attached": [placeholder_exp]}
            req_topic['children'] = {"attached": [placeholder_step]}

            mod_children.append(req_topic)

        if mod_children:
            mod_topic['children'] = {"attached": mod_children}
        root_children.append(mod_topic)

    if root_children:
        root['children'] = {"attached": root_children}

    content = [{
        "id": "sheet1",
        "class": "sheet",
        "title": "Sheet 1",
        "rootTopic": root,
    }]

    timestamp = int(_time.time() * 1000)
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    metadata = {"creator": {"name": "智测平台", "version": "1.0"}, "created": timestamp}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('content.json', json.dumps(content, ensure_ascii=False, indent=2))
        z.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2))
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))

    result = buf.getvalue()
    return result
