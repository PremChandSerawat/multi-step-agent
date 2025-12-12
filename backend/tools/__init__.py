from .calculate_oee import TOOL as CALCULATE_OEE, execute as exec_calculate_oee
from .find_bottleneck import TOOL as FIND_BOTTLENECK, execute as exec_find_bottleneck
from .get_alarm_log import TOOL as GET_ALARM_LOG, execute as exec_get_alarm_log
from .get_all_stations import TOOL as GET_ALL_STATIONS, execute as exec_get_all_stations
from .get_maintenance_schedule import (
    TOOL as GET_MAINTENANCE_SCHEDULE,
    execute as exec_get_maintenance_schedule,
)
from .get_product_mix import TOOL as GET_PRODUCT_MIX, execute as exec_get_product_mix
from .get_production_metrics import (
    TOOL as GET_PRODUCTION_METRICS,
    execute as exec_get_production_metrics,
)
from .get_recent_runs import TOOL as GET_RECENT_RUNS, execute as exec_get_recent_runs
from .get_scrap_summary import TOOL as GET_SCRAP_SUMMARY, execute as exec_get_scrap_summary
from .get_station import TOOL as GET_STATION, execute as exec_get_station
from .get_station_energy import TOOL as GET_STATION_ENERGY, execute as exec_get_station_energy
from .get_station_status import TOOL as GET_STATION_STATUS, execute as exec_get_station_status
from .get_stations_by_status import (
    TOOL as GET_STATIONS_BY_STATUS,
    execute as exec_get_stations_by_status,
)
from .update_station_status import (
    TOOL as UPDATE_STATION_STATUS,
    execute as exec_update_station_status,
)

TOOL_DEFINITIONS = [
    GET_ALL_STATIONS,
    GET_STATION,
    GET_STATION_STATUS,
    GET_PRODUCTION_METRICS,
    CALCULATE_OEE,
    FIND_BOTTLENECK,
    GET_STATIONS_BY_STATUS,
    GET_MAINTENANCE_SCHEDULE,
    UPDATE_STATION_STATUS,
    GET_RECENT_RUNS,
    GET_ALARM_LOG,
    GET_STATION_ENERGY,
    GET_SCRAP_SUMMARY,
    GET_PRODUCT_MIX,
]

EXECUTORS = {
    "get_all_stations": exec_get_all_stations,
    "get_station": exec_get_station,
    "get_station_status": exec_get_station_status,
    "get_production_metrics": exec_get_production_metrics,
    "calculate_oee": exec_calculate_oee,
    "find_bottleneck": exec_find_bottleneck,
    "get_stations_by_status": exec_get_stations_by_status,
    "get_maintenance_schedule": exec_get_maintenance_schedule,
    "update_station_status": exec_update_station_status,
    "get_recent_runs": exec_get_recent_runs,
    "get_alarm_log": exec_get_alarm_log,
    "get_station_energy": exec_get_station_energy,
    "get_scrap_summary": exec_get_scrap_summary,
    "get_product_mix": exec_get_product_mix,
}

__all__ = ["TOOL_DEFINITIONS", "EXECUTORS"]






