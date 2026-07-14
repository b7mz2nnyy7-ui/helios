"""Deterministic local end-to-end content workflow."""

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from agents.audience_research.agent import AudienceResearchAgent
from agents.audience_research.models import AudienceProfile
from agents.avatar.agent import AvatarAgent
from agents.avatar.models import AvatarProfile
from agents.creative_director.agent import CreativeDirectorAgent
from agents.creative_director.models import CreativeBrief
from agents.hook.agent import HookAgent
from agents.hook.models import OptimizedHook
from agents.knowledge.agent import KnowledgeAgent
from agents.knowledge.models import KnowledgeResponse
from agents.music.agent import MusicAgent
from agents.music.models import MusicProfile
from agents.script.agent import ScriptAgent
from agents.script.models import VideoScript
from agents.storyboard.agent import StoryboardAgent
from agents.storyboard.models import Storyboard
from agents.strategy.agent import StrategyAgent
from agents.strategy.models import ContentStrategy
from agents.trend_research.agent import TrendResearchAgent
from agents.trend_research.report import TrendReport
from agents.video_production.agent import VideoProductionAgent
from agents.voice.agent import VoiceAgent
from agents.voice.models import VoiceProfile
from engine.media.render_job import RenderJob
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.task import Task
from workflows.models import ContentPipelineResult

T = TypeVar("T")


class ContentPipeline:
    """Run the local content pipeline through HeliosRuntime."""

    def __init__(
        self,
        runtime: HeliosRuntime,
        agents: Sequence[BaseAgent] | None = None,
        task_id_generator: Callable[[str], str] | None = None,
    ) -> None:
        """Create a content pipeline for a runtime."""
        self.runtime = runtime
        self._task_id_generator = task_id_generator or self._default_task_id
        self._register_agents(list(agents) if agents is not None else self._default_agents())

    def run(
        self,
        query: str,
        language: str = "de",
        target_age_range: str = "18-34",
        target_duration_seconds: float = 30.0,
    ) -> ContentPipelineResult:
        """Run all content agents in sequence and return the render job."""
        clean_query = self._validate_text(query, "query")
        clean_language = self._validate_text(language, "language")
        clean_age_range = self._validate_text(target_age_range, "target_age_range")
        if target_duration_seconds <= 0:
            msg = "target_duration_seconds must be greater than 0."
            raise ValueError(msg)

        if not self.runtime.running:
            self.runtime.start()

        completed_task_ids: list[str] = []

        trend_report = self._submit(
            step="trend_research",
            title="Atlas Trend Research",
            capability=AgentCapability.TREND_RESEARCH,
            payload={"query": clean_query},
            expected_type=TrendReport,
            completed_task_ids=completed_task_ids,
        )
        audience_profile = self._submit(
            step="audience_research",
            title="Mira Audience Research",
            capability=AgentCapability.AUDIENCE_RESEARCH,
            payload={
                "topic": clean_query,
                "language": clean_language,
                "target_age_range": clean_age_range,
            },
            expected_type=AudienceProfile,
            completed_task_ids=completed_task_ids,
        )
        knowledge_response = self._submit(
            step="knowledge",
            title="Sage Knowledge Research",
            capability=AgentCapability.KNOWLEDGE,
            payload={"query": clean_query},
            expected_type=KnowledgeResponse,
            completed_task_ids=completed_task_ids,
        )
        content_strategy = self._submit(
            step="strategy",
            title="Nova Content Strategy",
            capability=AgentCapability.STRATEGY,
            payload={"trend_report": trend_report},
            expected_type=ContentStrategy,
            completed_task_ids=completed_task_ids,
        )
        video_script = self._submit(
            step="script",
            title="Orion Video Script",
            capability=AgentCapability.SCRIPT,
            payload={
                "trend_report": trend_report,
                "audience_profile": audience_profile,
                "knowledge_response": knowledge_response,
                "content_strategy": content_strategy,
            },
            expected_type=VideoScript,
            completed_task_ids=completed_task_ids,
        )
        optimized_hook = self._submit(
            step="hook",
            title="Apollo Hook Optimization",
            capability=AgentCapability.HOOK,
            payload={"video_script": video_script},
            expected_type=OptimizedHook,
            completed_task_ids=completed_task_ids,
        )
        storyboard = self._submit(
            step="storyboard",
            title="Lumen Storyboard",
            capability=AgentCapability.STORYBOARD,
            payload={
                "video_script": video_script,
                "optimized_hook": optimized_hook,
                "target_duration_seconds": target_duration_seconds,
            },
            expected_type=Storyboard,
            completed_task_ids=completed_task_ids,
        )
        creative_brief = self._submit(
            step="creative_director",
            title="Aether Creative Brief",
            capability=AgentCapability.CREATIVE_DIRECTION,
            payload={
                "storyboard": storyboard,
                "content_strategy": content_strategy,
                "audience_profile": audience_profile,
            },
            expected_type=CreativeBrief,
            completed_task_ids=completed_task_ids,
        )
        avatar_profile = self._submit(
            step="avatar",
            title="Echo Avatar Profile",
            capability=AgentCapability.AVATAR,
            payload={
                "creative_brief": creative_brief,
                "audience_profile": audience_profile,
            },
            expected_type=AvatarProfile,
            completed_task_ids=completed_task_ids,
        )
        voice_profile = self._submit(
            step="voice",
            title="Vox Voice Profile",
            capability=AgentCapability.VOICE,
            payload={
                "video_script": video_script,
                "avatar_profile": avatar_profile,
                "creative_brief": creative_brief,
                "language": clean_language,
            },
            expected_type=VoiceProfile,
            completed_task_ids=completed_task_ids,
        )
        music_profile = self._submit(
            step="music",
            title="Pulse Music Profile",
            capability=AgentCapability.MUSIC,
            payload={
                "creative_brief": creative_brief,
                "audience_profile": audience_profile,
                "video_script": video_script,
            },
            expected_type=MusicProfile,
            completed_task_ids=completed_task_ids,
        )
        render_job = self._submit(
            step="video_production",
            title="Forge Video Production Plan",
            capability=AgentCapability.VIDEO_PRODUCTION,
            payload={
                "storyboard": storyboard,
                "creative_brief": creative_brief,
                "avatar_profile": avatar_profile,
                "voice_profile": voice_profile,
                "music_profile": music_profile,
            },
            expected_type=RenderJob,
            completed_task_ids=completed_task_ids,
        )

        return ContentPipelineResult(
            query=clean_query,
            trend_report=trend_report,
            audience_profile=audience_profile,
            knowledge_response=knowledge_response,
            content_strategy=content_strategy,
            video_script=video_script,
            optimized_hook=optimized_hook,
            storyboard=storyboard,
            creative_brief=creative_brief,
            avatar_profile=avatar_profile,
            voice_profile=voice_profile,
            music_profile=music_profile,
            render_job=render_job,
            completed_task_ids=completed_task_ids,
        )

    def _submit(
        self,
        step: str,
        title: str,
        capability: AgentCapability,
        payload: dict[str, Any],
        expected_type: type[T],
        completed_task_ids: list[str],
    ) -> T:
        task = Task(
            task_id=self._task_id_generator(step),
            title=title,
            description=f"Run {title}.",
            priority=TaskPriority.MEDIUM,
            required_capability=capability,
            payload=payload,
        )
        result = self.runtime.submit_task(task)
        if not isinstance(result, expected_type):
            msg = f"{step} must return {expected_type.__name__}."
            raise TypeError(msg)

        completed_task_ids.append(task.task_id)
        return result

    def _register_agents(self, agents: list[BaseAgent]) -> None:
        for agent in agents:
            if not self.runtime.registry.exists(agent.agent_id):
                self.runtime.register(agent)

    def _default_agents(self) -> list[BaseAgent]:
        return [
            TrendResearchAgent(),
            AudienceResearchAgent(),
            KnowledgeAgent(),
            StrategyAgent(),
            ScriptAgent(),
            HookAgent(),
            StoryboardAgent(),
            CreativeDirectorAgent(),
            AvatarAgent(),
            VoiceAgent(),
            MusicAgent(),
            VideoProductionAgent(),
        ]

    def _default_task_id(self, step: str) -> str:
        return f"content-pipeline-{step}"

    def _validate_text(self, value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            msg = f"{field_name} must be a non-empty string."
            raise ValueError(msg)

        return value.strip()
