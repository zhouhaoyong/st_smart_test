"""用户默认头像生成工具。"""

from html import escape

from utils.oss_client import upload_file


AVATAR_BG_COLORS = (
    "#1677ff",
    "#52c41a",
    "#fa8c16",
    "#eb2f96",
    "#722ed1",
    "#13c2c2",
    "#f5222d",
    "#faad14",
)


def avatar_initial(real_name: str | None) -> str:
    """获取默认头像展示的首个字符。"""
    value = str(real_name or "用").strip()
    return value[:1].upper() if value else "用"


def build_default_avatar_svg(user_id: int, real_name: str | None) -> bytes:
    """生成固定画布、固定字号和固定留白的默认用户头像。"""
    color = AVATAR_BG_COLORS[int(user_id) % len(AVATAR_BG_COLORS)]
    initial = escape(avatar_initial(real_name))
    aria_label = escape(f"{real_name or '用户'}头像", quote=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="{aria_label}">
  <circle cx="64" cy="64" r="64" fill="{color}"/>
  <text x="64" y="64" dy="0.35em" text-anchor="middle" fill="#ffffff" font-family="Arial, 'Microsoft YaHei', sans-serif" font-size="54" font-weight="600">{initial}</text>
</svg>
'''
    return svg.encode("utf-8")


def create_default_avatar(user_id: int, real_name: str | None) -> str:
    """生成并保存默认头像，返回数据库应保存的文件引用。"""
    contents = build_default_avatar_svg(user_id, real_name)
    return upload_file(
        contents,
        "avatars",
        f"default-{user_id}.svg",
        "image/svg+xml",
    )
