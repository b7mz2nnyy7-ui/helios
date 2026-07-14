"""Models for local content workflows."""

from dataclasses import dataclass

from agents.audience_research.models import AudienceProfile
from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.hook.models import OptimizedHook
from agents.knowledge.models import KnowledgeResponse
from agents.music.models import MusicProfile
from agents.script.models import VideoScript
from agents.storyboard.models import Storyboard
from agents.strategy.models import ContentStrategy
from agents.trend_research.report import TrendReport
from agents.voice.models import VoiceProfile
from engine.media.render_job import RenderJob


@dataclass
class ContentPipelineResult:
    """Result of a complete local content production workflow."""

    query: str
    trend_report: TrendReport
    audience_profile: AudienceProfile
    knowledge_response: KnowledgeResponse
    content_strategy: ContentStrategy
    video_script: VideoScript
    optimized_hook: OptimizedHook
    storyboard: Storyboard
    creative_brief: CreativeBrief
    avatar_profile: AvatarProfile
    voice_profile: VoiceProfile
    music_profile: MusicProfile
    render_job: RenderJob
    completed_task_ids: list[str]

    def to_markdown(self) -> str:
        """Return the content pipeline result as Markdown."""
        completed_tasks = "\n".join(
            f"- {task_id}" for task_id in self.completed_task_ids
        )
        return (
            f"# Content Pipeline Result: {self.query}\n\n"
            f"## Trend Report\n\n{self.trend_report.summary}\n\n"
            f"## Audience Profile\n\n{self.audience_profile.summary}\n\n"
            f"## Knowledge Response\n\n{self.knowledge_response.summary}\n\n"
            f"## Content Strategy\n\n{self.content_strategy.summary}\n\n"
            f"## Video Script\n\n{self.video_script.title}\n\n"
            f"## Optimized Hook\n\n{self.optimized_hook.selected_hook.text}\n\n"
            f"## Storyboard\n\n{self.storyboard.summary}\n\n"
            f"## Creative Brief\n\n{self.creative_brief.summary}\n\n"
            f"## Avatar Profile\n\n{self.avatar_profile.summary}\n\n"
            f"## Voice Profile\n\n{self.voice_profile.summary}\n\n"
            f"## Music Profile\n\n{self.music_profile.summary}\n\n"
            f"## Render Job\n\n{self.render_job.job_id}\n\n"
            f"## Completed Tasks\n\n{completed_tasks}"
        )

