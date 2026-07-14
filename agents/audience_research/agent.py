"""Mira audience research agent."""

from agents.audience_research.mock_llm_provider import MockAudienceLLMProvider
from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class AudienceResearchAgent(BaseAgent):
    """Mira agent for creating structured audience profiles."""

    last_profile: AudienceProfile | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Mira audience research agent."""
        super().__init__(
            agent_id="audience_research",
            name="Mira",
            capabilities={AgentCapability.AUDIENCE_RESEARCH},
        )
        self.last_profile = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> AudienceProfile:
        """Create an audience profile from a research task."""
        if task.required_capability is not AgentCapability.AUDIENCE_RESEARCH:
            msg = "AudienceResearchAgent can only handle AUDIENCE_RESEARCH tasks."
            raise ValueError(msg)

        task.start()
        try:
            topic = self._get_required_text(task.payload.get("topic"), "topic")
            language = self._get_optional_text(task.payload.get("language"), "de")
            target_age_range = self._get_optional_text(
                task.payload.get("target_age_range"),
                "18-34",
            )
            llm_request = self._create_llm_request(topic, language, target_age_range)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            profile = self._create_profile(
                topic=topic,
                language=language,
                target_age_range=target_age_range,
                llm_response=llm_response,
            )
            self.last_profile = profile
            task.complete(profile)
            return profile
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockAudienceLLMProvider()))

        return selected_tools

    def _get_required_text(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            msg = f"{field_name} must be a non-empty string."
            raise ValueError(msg)

        return value.strip()

    def _get_optional_text(self, value: object, default: str) -> str:
        if value is None:
            return default

        if not isinstance(value, str) or not value.strip():
            msg = "optional text fields must be non-empty strings when provided."
            raise ValueError(msg)

        return value.strip()

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        topic: str,
        language: str,
        target_age_range: str,
    ) -> LLMRequest:
        return LLMRequest(
            system_prompt=(
                "Mira analysiert Zielgruppen für Social-Media-Content sachlich, "
                "datenorientiert und ohne stereotype Annahmen."
            ),
            user_prompt=(
                f"Topic: {topic}\n"
                f"Language: {language}\n"
                f"Target Age Range: {target_age_range}\n\n"
                "Analysiere folgende Bereiche:\n"
                "- Interessen\n"
                "- Probleme\n"
                "- Emotionen\n"
                "- Tonalität\n"
                "- Plattformpräferenzen"
            ),
        )

    def _create_profile(
        self,
        topic: str,
        language: str,
        target_age_range: str,
        llm_response: LLMResponse,
    ) -> AudienceProfile:
        lines = [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
        return AudienceProfile(
            topic=topic,
            target_age_range=target_age_range,
            language=language,
            interests=self._parse_prefixed_values(lines, "Interest: "),
            pain_points=self._parse_pain_points(lines),
            preferred_tone=self._parse_single_value(lines, "Tone: "),
            preferred_platforms=self._parse_prefixed_values(lines, "Platform: "),
            summary=self._parse_single_value(lines, "Summary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_single_value(self, lines: list[str], prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix)

        msg = f"LLM response must contain a {prefix.strip()} line."
        raise ValueError(msg)

    def _parse_prefixed_values(self, lines: list[str], prefix: str) -> list[str]:
        values = [
            line.removeprefix(prefix)
            for line in lines
            if line.startswith(prefix)
        ]
        if not values:
            msg = f"LLM response must contain at least one {prefix.strip()} line."
            raise ValueError(msg)

        return values

    def _parse_pain_points(self, lines: list[str]) -> list[AudiencePainPoint]:
        pain_points: list[AudiencePainPoint] = []
        for line in lines:
            if not line.startswith("PainPoint: "):
                continue

            parts = [
                part.strip()
                for part in line.removeprefix("PainPoint: ").split("|")
            ]
            if len(parts) != 3:
                msg = (
                    "LLM pain point lines must contain problem, severity and "
                    "emotional driver."
                )
                raise ValueError(msg)

            pain_points.append(
                AudiencePainPoint(
                    problem=parts[0],
                    severity=float(parts[1]),
                    emotional_driver=parts[2],
                ),
            )

        if not pain_points:
            msg = "LLM response must contain at least one PainPoint line."
            raise ValueError(msg)

        return pain_points
