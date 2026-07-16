"""Thread-safe in-memory repository for local Helios missions."""

from threading import RLock

from apps.api.mission_models import Mission


class MissionRepository:
    """Store immutable missions for the lifetime of one API application."""

    def __init__(self) -> None:
        """Create an empty isolated repository."""
        self._missions: dict[str, Mission] = {}
        self._lock = RLock()

    def register(self, mission: Mission) -> None:
        """Register a new mission with a unique ID."""
        with self._lock:
            if mission.mission_id in self._missions:
                msg = f"Mission '{mission.mission_id}' is already registered."
                raise ValueError(msg)
            self._missions[mission.mission_id] = mission

    def save(self, mission: Mission) -> None:
        """Replace an existing mission atomically."""
        with self._lock:
            if mission.mission_id not in self._missions:
                raise KeyError(mission.mission_id)
            self._missions[mission.mission_id] = mission

    def get(self, mission_id: str) -> Mission:
        """Return one mission or raise KeyError when it is unknown."""
        with self._lock:
            try:
                return self._missions[mission_id]
            except KeyError:
                raise KeyError(mission_id) from None

    def all(self) -> list[Mission]:
        """Return a newest-first snapshot of all missions."""
        with self._lock:
            return sorted(
                self._missions.values(),
                key=lambda mission: (mission.created_at, mission.mission_id),
                reverse=True,
            )

    def count(self) -> int:
        """Return the number of registered missions."""
        with self._lock:
            return len(self._missions)
