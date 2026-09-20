"""地址转经纬度工具接口。"""
from __future__ import annotations

import httpx

from core.config import settings

from ._shared import (
    APIRouter,
    AsyncSession,
    BaseModel,
    Depends,
    UnifiedException,
    get_current_active_user,
    get_db,
    log_user_operation,
    success_response,
)

router = APIRouter()


class GeocodeRequest(BaseModel):
    address: str


def _as_text(value) -> str:
    """将高德返回的可选字段统一为字符串，避免单字段异常导致整轮失败。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            text = _as_text(item)
            if text:
                return text
    return ""


def _normalize_geocode_result(payload: dict, source_address: str) -> dict:
    """提取固定返回结构，兼容高德缺少字段或字段类型变化的情况。"""
    geocodes = payload.get("geocodes")
    item = geocodes[0] if isinstance(geocodes, list) and geocodes and isinstance(geocodes[0], dict) else {}
    component = item.get("addressComponent") if isinstance(item.get("addressComponent"), dict) else {}

    location = _as_text(item.get("location"))
    longitude = ""
    latitude = ""
    if "," in location:
        longitude, latitude = [part.strip() for part in location.split(",", 1)]

    return {
        "address": source_address,
        "formatted_address": _as_text(item.get("formatted_address")) or source_address,
        "location": location,
        "longitude": longitude,
        "latitude": latitude,
        "level": _as_text(item.get("level")),
        "province": _as_text(component.get("province")),
        "city": _as_text(component.get("city")),
        "district": _as_text(component.get("district")),
        "adcode": _as_text(component.get("adcode")),
    }


def _normalize_regeocode_result(payload: dict, longitude: str, latitude: str) -> dict:
    """提取逆地理编码的固定返回结构。"""
    regeocode = payload.get("regeocode") if isinstance(payload.get("regeocode"), dict) else {}
    component = regeocode.get("addressComponent") if isinstance(regeocode.get("addressComponent"), dict) else {}
    street_number = component.get("streetNumber") if isinstance(component.get("streetNumber"), dict) else {}

    return {
        "longitude": longitude,
        "latitude": latitude,
        "location": f"{longitude},{latitude}",
        "formatted_address": _as_text(regeocode.get("formatted_address")),
        "province": _as_text(component.get("province")),
        "city": _as_text(component.get("city")),
        "district": _as_text(component.get("district")),
        "township": _as_text(component.get("township")),
        "street": _as_text(street_number.get("street")),
        "number": _as_text(street_number.get("number")),
        "adcode": _as_text(component.get("adcode")),
    }


@router.post("/geocode")
async def geocode_address(
    data: GeocodeRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    address = (data.address or "").strip()
    if not address:
        raise UnifiedException(code=400, message="请输入地址")
    if len(address.encode("utf-8")) > 128:
        raise UnifiedException(code=400, message="地址不能超过128个字节")

    api_key = (settings.AMAP_WEB_SERVICE_KEY or "").strip()
    if not api_key:
        raise UnifiedException(code=500, message="高德地图服务未配置，请联系管理员")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"key": api_key, "address": address, "output": "JSON"},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        raise UnifiedException(code=500, message="高德地图服务请求超时，请稍后重试")
    except (httpx.HTTPError, ValueError):
        raise UnifiedException(code=500, message="高德地图服务暂时不可用，请稍后重试")

    if not isinstance(payload, dict) or payload.get("status") != "1":
        info = _as_text(payload.get("info")) if isinstance(payload, dict) else ""
        raise UnifiedException(code=400, message=f"地址查询失败：{info or '请检查地址后重试'}")

    result = _normalize_geocode_result(payload, address)
    if not result["location"] or not result["longitude"] or not result["latitude"]:
        raise UnifiedException(code=400, message="未找到匹配地址，请补充省、市、区和街道信息")

    await log_user_operation(
        db=db,
        user=current_user,
        module="toolbox",
        operation="地址转经纬度",
        target_name="地址转经纬度",
        description="查询地址对应的经纬度",
        details={"address_length": len(address), "level": result["level"]},
    )
    return success_response(data=result, message="查询成功")


class ReverseGeocodeRequest(BaseModel):
    longitude: str
    latitude: str


@router.post("/regeo")
async def reverse_geocode(
    data: ReverseGeocodeRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    longitude = (data.longitude or "").strip()
    latitude = (data.latitude or "").strip()
    try:
        longitude_value = float(longitude)
        latitude_value = float(latitude)
    except (TypeError, ValueError):
        raise UnifiedException(code=400, message="请输入有效的经度和纬度")

    if not -180 <= longitude_value <= 180:
        raise UnifiedException(code=400, message="经度范围应为 -180 至 180")
    if not -90 <= latitude_value <= 90:
        raise UnifiedException(code=400, message="纬度范围应为 -90 至 90")

    api_key = (settings.AMAP_WEB_SERVICE_KEY or "").strip()
    if not api_key:
        raise UnifiedException(code=500, message="高德地图服务未配置，请联系管理员")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://restapi.amap.com/v3/geocode/regeo",
                params={
                    "key": api_key,
                    "location": f"{longitude},{latitude}",
                    "output": "JSON",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        raise UnifiedException(code=500, message="高德地图服务请求超时，请稍后重试")
    except (httpx.HTTPError, ValueError):
        raise UnifiedException(code=500, message="高德地图服务暂时不可用，请稍后重试")

    if not isinstance(payload, dict) or payload.get("status") != "1":
        info = _as_text(payload.get("info")) if isinstance(payload, dict) else ""
        raise UnifiedException(code=400, message=f"地址查询失败：{info or '请检查坐标后重试'}")

    result = _normalize_regeocode_result(payload, longitude, latitude)
    if not result["formatted_address"]:
        raise UnifiedException(code=400, message="未找到该坐标对应的中文地址")

    await log_user_operation(
        db=db,
        user=current_user,
        module="toolbox",
        operation="经纬度转地址",
        target_name="经纬度转地址",
        description="查询经纬度对应的中文地址",
        details={"longitude": longitude, "latitude": latitude},
    )
    return success_response(data=result, message="查询成功")
