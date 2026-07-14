"""Integration tests for the local end-to-end content pipeline."""

import unittest

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
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.runtime.runtime import HeliosRuntime
from workflows.content_pipeline import ContentPipeline
from workflows.models import ContentPipelineResult


class ContentPipelineIntegrationTestCase(unittest.TestCase):
    """End-to-end tests for the full mock content pipeline."""

    def test_full_mock_pipeline_returns_render_job(self) -> None:
        """The full local workflow runs from query to pending RenderJob."""
        runtime = HeliosRuntime()
        pipeline = ContentPipeline(runtime)

        result = pipeline.run("AI Agents")

        self.assertIsInstance(result, ContentPipelineResult)
        self.assertIsInstance(result.trend_report, TrendReport)
        self.assertIsInstance(result.audience_profile, AudienceProfile)
        self.assertIsInstance(result.knowledge_response, KnowledgeResponse)
        self.assertIsInstance(result.content_strategy, ContentStrategy)
        self.assertIsInstance(result.video_script, VideoScript)
        self.assertIsInstance(result.optimized_hook, OptimizedHook)
        self.assertIsInstance(result.storyboard, Storyboard)
        self.assertIsInstance(result.creative_brief, CreativeBrief)
        self.assertIsInstance(result.avatar_profile, AvatarProfile)
        self.assertIsInstance(result.voice_profile, VoiceProfile)
        self.assertIsInstance(result.music_profile, MusicProfile)
        self.assertIsInstance(result.render_job, RenderJob)
        self.assertIs(result.render_job.status, RenderJobStatus.PENDING)
        self.assertEqual(len(result.completed_task_ids), 12)
        self.assertTrue(runtime.running)


if __name__ == "__main__":
    unittest.main()
