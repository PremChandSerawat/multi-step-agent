"""
Mock Production Line Simulator
Simulates production line data with stations, metrics, and calculations.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional


@dataclass
class Station:
    """Represents a production station."""

    id: str
    name: str
    status: str  # "running", "idle", "maintenance", "error"
    throughput: float  # units per hour
    efficiency: float  # percentage
    temperature: float  # celsius
    pressure: float  # psi
    last_maintenance: str
    uptime: float  # percentage


@dataclass
class ProductionMetrics:
    """Overall production metrics."""

    total_units_produced: int
    target_units: int
    efficiency: float
    downtime_hours: float
    quality_rate: float
    energy_consumption: float  # kWh
    timestamp: str


class ProductionLineSimulator:
    """Simulates a production line with multiple stations."""

    def __init__(self):
        self.stations: Dict[str, Station] = {}
        self.metrics_history: List[ProductionMetrics] = []
        self.runs: List[Dict] = []
        self.alarms: List[Dict] = []
        self.energy: Dict[str, Dict] = {}
        self._initialize_stations()
        self._load_sample_runs()
        self._load_sample_alarms()
        self._load_energy_snapshots()

    def _initialize_stations(self) -> None:
        """Initialize mock production stations."""
        station_configs = [
            {"id": "ST001", "name": "Assembly Station 1"},
            {"id": "ST002", "name": "Quality Check Station"},
            {"id": "ST003", "name": "Packaging Station"},
            {"id": "ST004", "name": "Assembly Station 2"},
            {"id": "ST005", "name": "Testing Station"},
        ]

        for config in station_configs:
            self.stations[config["id"]] = Station(
                id=config["id"],
                name=config["name"],
                status=random.choice(
                    ["running", "running", "running", "idle", "maintenance"]
                ),
                throughput=random.uniform(50, 150),
                efficiency=random.uniform(75, 98),
                temperature=random.uniform(20, 45),
                pressure=random.uniform(10, 50),
                last_maintenance=(
                    datetime.now() - timedelta(days=random.randint(1, 30))
                ).isoformat(),
                uptime=random.uniform(85, 99),
            )

    def get_all_stations(self) -> List[Dict]:
        """Get all station data."""
        return [asdict(station) for station in self.stations.values()]

    def get_station(self, station_id: str) -> Optional[Dict]:
        """Get data for a specific station."""
        station = self.stations.get(station_id)
        return asdict(station) if station else None

    def get_station_status(self, station_id: str) -> Optional[Dict]:
        """Get status information for a specific station."""
        station = self.stations.get(station_id)
        if not station:
            return None
        return {
            "id": station.id,
            "name": station.name,
            "status": station.status,
            "uptime": station.uptime,
            "efficiency": station.efficiency,
        }

    def get_production_metrics(self) -> Dict:
        """Get overall production metrics."""
        total_units = sum(
            int(station.throughput * 0.8)
            for station in self.stations.values()
            if station.status == "running"
        )
        avg_efficiency = (
            sum(station.efficiency for station in self.stations.values())
            / len(self.stations)
        )
        downtime = sum(
            1 for station in self.stations.values() if station.status != "running"
        )

        metrics = ProductionMetrics(
            total_units_produced=total_units,
            target_units=1000,
            efficiency=avg_efficiency,
            downtime_hours=downtime * 0.5,
            quality_rate=random.uniform(92, 99),
            energy_consumption=random.uniform(500, 1200),
            timestamp=datetime.now().isoformat(),
        )

        self.metrics_history.append(metrics)
        return asdict(metrics)

    # -----------------------------
    # Extended, dataset-inspired APIs
    # -----------------------------

    def _load_sample_runs(self) -> None:
        """
        Load a small synthetic run log inspired by open manufacturing datasets
        (e.g., the public SECOM and Bosch quality datasets). Values are
        representative, not real.
        """
        now = datetime.now()
        sample = [
            {
                "run_id": "R-2401",
                "product": "Widget-A",
                "line": "L1",
                "shift": "A",
                "good_units": 420,
                "scrap_units": 6,
                "cycle_time_avg_s": 5.8,
                "defect_codes": ["D14"],
                "started_at": (now - timedelta(hours=6)).isoformat(),
                "ended_at": (now - timedelta(hours=4)).isoformat(),
            },
            {
                "run_id": "R-2402",
                "product": "Widget-B",
                "line": "L2",
                "shift": "A",
                "good_units": 380,
                "scrap_units": 12,
                "cycle_time_avg_s": 6.1,
                "defect_codes": ["D07", "D21"],
                "started_at": (now - timedelta(hours=4)).isoformat(),
                "ended_at": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "run_id": "R-2403",
                "product": "Widget-A",
                "line": "L1",
                "shift": "B",
                "good_units": 450,
                "scrap_units": 4,
                "cycle_time_avg_s": 5.5,
                "defect_codes": [],
                "started_at": (now - timedelta(hours=2)).isoformat(),
                "ended_at": (now - timedelta(minutes=10)).isoformat(),
            },
            {
                "run_id": "R-2404",
                "product": "Widget-C",
                "line": "L3",
                "shift": "B",
                "good_units": 300,
                "scrap_units": 15,
                "cycle_time_avg_s": 7.2,
                "defect_codes": ["D04", "D19"],
                "started_at": (now - timedelta(hours=3)).isoformat(),
                "ended_at": (now - timedelta(hours=1, minutes=20)).isoformat(),
            },
        ]
        self.runs = sample

    def _load_sample_alarms(self) -> None:
        """Seed an alarm log with realistic manufacturing alerts."""
        now = datetime.now()
        self.alarms = [
            {
                "id": "AL-9001",
                "station_id": "ST002",
                "severity": "high",
                "code": "VISION_MISALIGN",
                "message": "Vision system detected part misalignment",
                "timestamp": (now - timedelta(minutes=35)).isoformat(),
            },
            {
                "id": "AL-9002",
                "station_id": "ST003",
                "severity": "medium",
                "code": "LABEL_LOW_CONTRAST",
                "message": "Label contrast below threshold",
                "timestamp": (now - timedelta(hours=1, minutes=5)).isoformat(),
            },
            {
                "id": "AL-9003",
                "station_id": "ST005",
                "severity": "low",
                "code": "TEMP_DRIFT",
                "message": "Chamber temperature drifted +1.5C",
                "timestamp": (now - timedelta(hours=2, minutes=10)).isoformat(),
            },
        ]

    def _load_energy_snapshots(self) -> None:
        """Simulated energy consumption snapshot per station."""
        self.energy = {
            sid: {
                "station_id": sid,
                "kwh_last_hour": round(random.uniform(8, 18), 2),
                "kwh_last_24h": round(random.uniform(160, 360), 2),
                "peak_kw": round(random.uniform(4, 9), 2),
            }
            for sid in self.stations.keys()
        }

    def get_recent_runs(self, limit: int = 5) -> List[Dict]:
        """Return recent production runs sorted by end time."""
        return sorted(self.runs, key=lambda r: r["ended_at"], reverse=True)[:limit]

    def get_alarm_log(self, limit: int = 10) -> List[Dict]:
        """Return recent alarms (newest first)."""
        return sorted(self.alarms, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def get_station_energy(self, station_id: str) -> Dict:
        """Energy snapshot for a station."""
        if station_id not in self.energy:
            return {"error": f"Station {station_id} not found"}
        return self.energy[station_id]

    def get_scrap_summary(self) -> Dict:
        """Aggregate scrap rate and top defect codes."""
        total_good = sum(r["good_units"] for r in self.runs)
        total_scrap = sum(r["scrap_units"] for r in self.runs)
        scrap_rate = (total_scrap / (total_good + total_scrap)) * 100 if total_good else 0

        defect_counts: Dict[str, int] = {}
        for run in self.runs:
            for code in run["defect_codes"]:
                defect_counts[code] = defect_counts.get(code, 0) + 1

        top_defects = sorted(
            [{"code": c, "count": n} for c, n in defect_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "total_good": total_good,
            "total_scrap": total_scrap,
            "scrap_rate": scrap_rate,
            "top_defects": top_defects,
        }

    def get_product_mix(self) -> List[Dict]:
        """Product mix by counts."""
        counts: Dict[str, int] = {}
        for run in self.runs:
            counts[run["product"]] = counts.get(run["product"], 0) + run["good_units"]
        return [{"product": p, "good_units": n} for p, n in counts.items()]

    def calculate_oee(self, station_id: Optional[str] = None) -> Dict:
        """Calculate Overall Equipment Effectiveness (OEE)."""
        if station_id:
            station = self.stations.get(station_id)
            if not station:
                return {"error": f"Station {station_id} not found"}

            availability = station.uptime / 100
            performance = station.efficiency / 100
            quality = random.uniform(0.90, 0.98)
            oee = availability * performance * quality * 100

            return {
                "station_id": station_id,
                "availability": availability * 100,
                "performance": performance * 100,
                "quality": quality * 100,
                "oee": oee,
            }

        stations = list(self.stations.values())
        avg_availability = sum(s.uptime for s in stations) / len(stations)
        avg_performance = sum(s.efficiency for s in stations) / len(stations)
        quality = random.uniform(0.90, 0.98)
        oee = (avg_availability / 100) * (avg_performance / 100) * quality * 100

        return {
            "overall_oee": oee,
            "average_availability": avg_availability,
            "average_performance": avg_performance,
            "quality": quality * 100,
        }

    def find_bottleneck(self, stations: List[str] = None) -> Dict:
        """Identify the production bottleneck.
        
        Args:
            stations: Optional list of station IDs to analyze. 
                      If not provided, defaults to all running stations.
        """
        print(f"Stations----------: {stations}")
        if stations is not None:
            # Use provided station IDs
            station_list = [
                self.stations[sid] for sid in stations if sid in self.stations
            ]
        else:
            # Default to all running stations
            station_list = [
                s for s in self.stations.values() if s.status == "running"
            ]
        
        if not station_list:
            return {"bottleneck": "No running stations", "throughput": 0}

        bottleneck = min(station_list, key=lambda s: s.throughput)
        result = {
            "bottleneck_station_id": bottleneck.id,
            "bottleneck_station_name": bottleneck.name,
            "throughput": bottleneck.throughput,
            "efficiency": bottleneck.efficiency,
            "status": bottleneck.status,
            "recommendation": (
                f"Optimize {bottleneck.name} to improve overall throughput"
            ),
        }

        print(f"Result----------: {result}")
        return result

    def get_stations_by_status(self, status: str) -> List[Dict]:
        """Get all stations with a specific status."""
        return [asdict(s) for s in self.stations.values() if s.status == status]

    def get_maintenance_schedule(self) -> List[Dict]:
        """Get maintenance schedule based on last maintenance dates."""
        schedule = []
        for station in self.stations.values():
            last_maint = datetime.fromisoformat(station.last_maintenance)
            days_since = (datetime.now() - last_maint).days
            days_until = max(0, 30 - days_since)

            schedule.append(
                {
                    "station_id": station.id,
                    "station_name": station.name,
                    "days_since_maintenance": days_since,
                    "days_until_next": days_until,
                    "priority": (
                        "high" if days_since > 25 else "medium" if days_since > 20 else "low"
                    ),
                }
            )

        return sorted(
            schedule, key=lambda x: x["days_since_maintenance"], reverse=True
        )

    def update_station_status(self, station_id: str, status: str) -> Dict:
        """Update a station's status."""
        if station_id not in self.stations:
            return {"error": f"Station {station_id} not found"}

        valid_statuses = ["running", "idle", "maintenance", "error"]
        if status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

        self.stations[station_id].status = status
        return {"success": True, "station_id": station_id, "new_status": status}


# Global simulator instance
simulator = ProductionLineSimulator()

