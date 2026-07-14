"""Run the deterministic content pipeline and write a Markdown report."""

import argparse
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.runtime.runtime import HeliosRuntime  # noqa: E402
from workflows.content_pipeline import ContentPipeline  # noqa: E402
from workflows.models import ContentPipelineResult  # noqa: E402


@dataclass(frozen=True)
class ContentPipelineDemoResult:
    """Result data produced by a successful local pipeline demo."""

    pipeline_result: ContentPipelineResult
    language: str
    target_age_range: str
    target_duration_seconds: float
    markdown_path: Path


DemoRunner = Callable[
    [str, str, str, float, Path],
    ContentPipelineDemoResult,
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and validate command-line arguments for the demo."""
    parser = argparse.ArgumentParser(
        description="Run the local deterministic Helios content pipeline.",
    )
    parser.add_argument("query", help="Topic to process through the content pipeline.")
    parser.add_argument("--language", default="de", help="Audience language.")
    parser.add_argument(
        "--age-range",
        default="18-34",
        help="Target audience age range.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Target video duration in seconds.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output"),
        help="Directory for the generated Markdown report.",
    )
    args = parser.parse_args(argv)
    args.query = _validate_text(args.query, "query")
    args.language = _validate_text(args.language, "language")
    args.age_range = _validate_text(args.age_range, "age_range")
    if args.duration <= 0:
        msg = "duration must be greater than 0."
        raise ValueError(msg)

    return args


def slugify_query(query: str) -> str:
    """Return a safe lowercase ASCII slug for a query."""
    clean_query = _validate_text(query, "query")
    normalized = unicodedata.normalize("NFKD", clean_query)
    ascii_query = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_query.lower()).strip("-")
    if not slug:
        msg = "query must contain at least one letter or number."
        raise ValueError(msg)

    return slug


def resolve_output_path(output_dir: Path, query: str) -> Path:
    """Return the first available safe report path for a query."""
    directory = output_dir.expanduser().resolve()
    slug = slugify_query(query)
    base_name = f"content-pipeline-{slug}"
    candidate = directory / f"{base_name}.md"
    suffix = 2

    while candidate.exists():
        candidate = directory / f"{base_name}-{suffix}.md"
        suffix += 1

    if candidate.parent != directory:
        msg = "resolved output path must remain inside output_dir."
        raise ValueError(msg)

    return candidate


def run_demo(
    query: str,
    language: str = "de",
    target_age_range: str = "18-34",
    target_duration_seconds: float = 30.0,
    output_dir: Path = Path("./output"),
    pipeline: ContentPipeline | None = None,
) -> ContentPipelineDemoResult:
    """Run the existing content pipeline and persist its Markdown report."""
    clean_query = _validate_text(query, "query")
    clean_language = _validate_text(language, "language")
    clean_age_range = _validate_text(target_age_range, "target_age_range")
    if target_duration_seconds <= 0:
        msg = "target_duration_seconds must be greater than 0."
        raise ValueError(msg)

    selected_pipeline = pipeline or ContentPipeline(HeliosRuntime())
    pipeline_result = selected_pipeline.run(
        clean_query,
        language=clean_language,
        target_age_range=clean_age_range,
        target_duration_seconds=target_duration_seconds,
    )

    directory = output_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = resolve_output_path(directory, clean_query)
    markdown = format_markdown(
        pipeline_result,
        language=clean_language,
        target_age_range=clean_age_range,
        target_duration_seconds=target_duration_seconds,
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    return ContentPipelineDemoResult(
        pipeline_result=pipeline_result,
        language=clean_language,
        target_age_range=clean_age_range,
        target_duration_seconds=target_duration_seconds,
        markdown_path=markdown_path,
    )


def format_markdown(
    result: ContentPipelineResult,
    language: str,
    target_age_range: str,
    target_duration_seconds: float,
) -> str:
    """Format a complete pipeline result as a readable Markdown report."""
    task_ids = "\n".join(f"- {task_id}" for task_id in result.completed_task_ids)
    audience = _format_audience_profile(result)
    knowledge = _format_knowledge_response(result)
    strategy = _format_content_strategy(result)
    render_job = result.render_job

    sections = [
        "# Local Content Pipeline Demo",
        (
            "## Run Configuration\n\n"
            f"- Query: {result.query}\n"
            f"- Language: {language}\n"
            f"- Target Age Range: {target_age_range}\n"
            f"- Target Duration: {target_duration_seconds}s\n"
            f"- Completed Tasks: {len(result.completed_task_ids)}"
        ),
        f"## Completed Task IDs\n\n{task_ids}",
        _section("Trend Report", result.trend_report.to_markdown()),
        _section("Audience Profile", audience),
        _section("Knowledge Response", knowledge),
        _section("Content Strategy", strategy),
        _section("Video Script", result.video_script.to_markdown()),
        _section("Optimized Hook", result.optimized_hook.to_markdown()),
        _section("Storyboard", result.storyboard.to_markdown()),
        _section("Creative Brief", result.creative_brief.to_markdown()),
        _section("Avatar Profile", result.avatar_profile.to_markdown()),
        _section("Voice Profile", result.voice_profile.to_markdown()),
        _section("Music Profile", result.music_profile.to_markdown()),
        (
            "## RenderJob\n\n"
            f"- RenderJob ID: {render_job.job_id}\n"
            f"- Provider: {render_job.provider}\n"
            f"- RenderJob Status: {render_job.status.value}"
        ),
        _section("VideoProductionPlan", render_job.plan.to_markdown()),
    ]
    return "\n\n".join(sections) + "\n"


def format_summary(result: ContentPipelineDemoResult) -> str:
    """Format the compact terminal summary for a successful run."""
    pipeline_result = result.pipeline_result
    render_job = pipeline_result.render_job
    return "\n".join(
        [
            f"Query: {pipeline_result.query}",
            "Status: COMPLETED",
            f"Abgeschlossene Tasks: {len(pipeline_result.completed_task_ids)}",
            f"Script-Titel: {pipeline_result.video_script.title}",
            f"Ausgewählter Hook: {pipeline_result.optimized_hook.selected_hook.text}",
            f"Storyboard-Szenen: {len(pipeline_result.storyboard.scenes)}",
            f"Zielplattform: {render_job.plan.target_platform}",
            f"Gesamtdauer: {render_job.plan.total_duration_seconds}s",
            f"RenderJob-ID: {render_job.job_id}",
            f"RenderJob-Status: {render_job.status.value}",
            f"Markdown-Datei: {result.markdown_path}",
        ],
    )


def main(
    argv: Sequence[str] | None = None,
    runner: DemoRunner = run_demo,
) -> int:
    """Run the content pipeline demo command and return its exit code."""
    try:
        args = parse_args(argv)
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    except Exception as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1

    try:
        result = runner(
            args.query,
            args.language,
            args.age_range,
            args.duration,
            args.output_dir,
        )
    except Exception as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1

    print(format_summary(result))
    return 0


def _validate_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field_name} must be a non-empty string."
        raise ValueError(msg)

    return value.strip()


def _section(title: str, content: str) -> str:
    return f"## {title}\n\n{content.strip()}"


def _format_audience_profile(result: ContentPipelineResult) -> str:
    profile = result.audience_profile
    interests = "\n".join(f"- {interest}" for interest in profile.interests)
    pain_points = "\n".join(
        (
            f"- {pain_point.problem} | severity={pain_point.severity} | "
            f"emotion={pain_point.emotional_driver}"
        )
        for pain_point in profile.pain_points
    )
    platforms = ", ".join(profile.preferred_platforms)
    return (
        f"Topic: {profile.topic}\n\n"
        f"Language: {profile.language}\n\n"
        f"Target Age Range: {profile.target_age_range}\n\n"
        f"### Interests\n\n{interests}\n\n"
        f"### Pain Points\n\n{pain_points}\n\n"
        f"Preferred Tone: {profile.preferred_tone}\n\n"
        f"Preferred Platforms: {platforms}\n\n"
        f"Summary: {profile.summary}\n\n"
        f"Generated by: {profile.generated_by}"
    )


def _format_knowledge_response(result: ContentPipelineResult) -> str:
    response = result.knowledge_response
    items = "\n".join(
        (
            f"- {item.title} | category={item.category.value} | "
            f"confidence={item.confidence} | source={item.source}\n"
            f"  {item.content}"
        )
        for item in response.items
    )
    return (
        f"Query: {response.query}\n\n"
        f"Summary: {response.summary}\n\n"
        f"### Knowledge Items\n\n{items}\n\n"
        f"Generated by: {response.generated_by}"
    )


def _format_content_strategy(result: ContentPipelineResult) -> str:
    strategy = result.content_strategy
    ideas = "\n".join(
        (
            f"- {idea.title} | angle={idea.angle} | "
            f"platform={idea.target_platform} | reason={idea.reason}"
        )
        for idea in strategy.ideas
    )
    return (
        f"Query: {strategy.query}\n\n"
        f"Summary: {strategy.summary}\n\n"
        f"### Content Ideas\n\n{ideas}\n\n"
        f"Generated by: {strategy.generated_by}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
