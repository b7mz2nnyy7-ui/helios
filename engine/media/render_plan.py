"""Provider-neutral video render plan models."""

from dataclasses import dataclass, field


@dataclass
class RenderScene:
    """A scene instruction inside a video production plan."""

    scene_number: int
    duration_seconds: float
    camera_instruction: str
    visual_instruction: str
    voice_instruction: str
    music_instruction: str
    transition: str

    def __post_init__(self) -> None:
        """Validate render scene values."""
        if self.scene_number <= 0:
            msg = "scene_number must be greater than 0."
            raise ValueError(msg)

        if self.duration_seconds <= 0:
            msg = "duration_seconds must be greater than 0."
            raise ValueError(msg)


@dataclass
class VideoProductionPlan:
    """A provider-neutral plan for producing a video."""

    plan_id: str
    title: str
    target_platform: str
    scenes: list[RenderScene]
    summary: str
    total_duration_seconds: float = field(init=False)

    def __post_init__(self) -> None:
        """Validate production plan values and calculate duration."""
        if not self.scenes:
            msg = "scenes must contain at least one scene."
            raise ValueError(msg)

        self.total_duration_seconds = sum(
            scene.duration_seconds for scene in self.scenes
        )
        if self.total_duration_seconds <= 0:
            msg = "total_duration_seconds must be greater than 0."
            raise ValueError(msg)

    def to_markdown(self) -> str:
        """Return the production plan as Markdown."""
        scene_blocks = "\n\n".join(
            (
                f"## Scene {scene.scene_number}\n\n"
                f"- Duration: {scene.duration_seconds}s\n"
                f"- Camera: {scene.camera_instruction}\n"
                f"- Visual: {scene.visual_instruction}\n"
                f"- Voice: {scene.voice_instruction}\n"
                f"- Music: {scene.music_instruction}\n"
                f"- Transition: {scene.transition}"
            )
            for scene in self.scenes
        )
        return (
            f"# {self.title}\n\n"
            f"Plan ID: {self.plan_id}\n\n"
            f"Target Platform: {self.target_platform}\n\n"
            f"Total Duration: {self.total_duration_seconds}s\n\n"
            f"{scene_blocks}\n\n"
            f"## Summary\n\n{self.summary}"
        )
