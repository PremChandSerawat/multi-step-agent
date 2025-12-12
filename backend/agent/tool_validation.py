from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Tuple, Type

from pydantic import BaseModel, Field, ValidationError


class EmptyArgs(BaseModel):
    """Tools that accept no arguments."""

    class Config:
        extra = "ignore"


class StationArgs(BaseModel):
    station_id: str = Field(..., min_length=1)

    class Config:
        extra = "ignore"


class OptionalStationArgs(BaseModel):
    station_id: Optional[str] = Field(default=None, min_length=1)

    class Config:
        extra = "ignore"


class StatusArgs(BaseModel):
    status: Literal["running", "idle", "maintenance", "error"]

    class Config:
        extra = "ignore"


class UpdateStationArgs(BaseModel):
    station_id: str = Field(..., min_length=1)
    status: Literal["running", "idle", "maintenance", "error"]

    class Config:
        extra = "ignore"


class RecentRunsArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=500)

    class Config:
        extra = "ignore"


class AlarmLogArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=500)

    class Config:
        extra = "ignore"


VALIDATOR_MAP: Dict[str, Type[BaseModel]] = {
    "get_all_stations": EmptyArgs,
    "get_station": StationArgs,
    "get_station_status": StationArgs,
    "get_production_metrics": EmptyArgs,
    "calculate_oee": OptionalStationArgs,
    "find_bottleneck": EmptyArgs,
    "get_stations_by_status": StatusArgs,
    "get_maintenance_schedule": EmptyArgs,
    "update_station_status": UpdateStationArgs,
    "get_recent_runs": RecentRunsArgs,
    "get_alarm_log": AlarmLogArgs,
    "get_station_energy": StationArgs,
    "get_scrap_summary": EmptyArgs,
    "get_product_mix": EmptyArgs,
}


def _model_dump(model: BaseModel) -> Dict[str, Any]:
    """Compat helper for Pydantic v1 vs v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def _validate(model_cls: Type[BaseModel], raw_args: Dict[str, Any] | None) -> Dict[str, Any]:
    data = raw_args or {}
    if hasattr(model_cls, "model_validate"):
        model = model_cls.model_validate(data)  # type: ignore[attr-defined]
    else:
        model = model_cls.parse_obj(data)
    return _model_dump(model)


def validate_tool_args(tool_name: str, raw_args: Dict[str, Any] | None) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    Validate and sanitize tool arguments coming from the LLM.

    Returns (validated_args, error_message). When validation fails or the tool
    is unknown, validated_args is None and error_message contains details.
    """
    model_cls = VALIDATOR_MAP.get(tool_name)
    if not model_cls:
        return None, f"Unknown tool: {tool_name}"
    try:
        return _validate(model_cls, raw_args), None
    except ValidationError as exc:
        return None, exc.json()
