"""Tests for the Helios company architecture metadata."""

import unittest
from dataclasses import FrozenInstanceError

from engine.company.agent_definition import AgentDefinition
from engine.company.blueprint import HELIOS_COMPANY_BLUEPRINT
from engine.company.company_registry import CompanyRegistry
from engine.company.department import Department
from engine.company import (
    AgentDefinition as ExportedAgentDefinition,
    CompanyRegistry as ExportedCompanyRegistry,
    Department as ExportedDepartment,
    HELIOS_COMPANY_BLUEPRINT as EXPORTED_HELIOS_COMPANY_BLUEPRINT,
)
from engine.runtime.capability import AgentCapability


def create_definition(
    agent_id: str = "agent-1",
    department: Department = Department.RESEARCH,
    capability: str = "TREND_RESEARCH",
) -> AgentDefinition:
    """Create an agent definition for tests."""
    return AgentDefinition(
        agent_id=agent_id,
        display_name="Test Agent",
        department=department,
        capability=capability,
        description="A test definition.",
        responsibilities=("Do the test work",),
        inputs=("input",),
        outputs=("output",),
        required_tools=("tool",),
        memory_access=("memory",),
        event_subscriptions=("event.created",),
    )


class DepartmentTestCase(unittest.TestCase):
    """Tests for Department enum values."""

    def test_department_enum_contains_required_values(self) -> None:
        """Department contains all required company departments."""
        expected_values = {
            "EXECUTIVE",
            "OPERATIONS",
            "RESEARCH",
            "STRATEGY",
            "KNOWLEDGE",
            "WRITING",
            "CREATIVE",
            "PRODUCTION",
            "DISTRIBUTION",
            "ANALYTICS",
            "MEMORY",
            "OPTIMIZATION",
            "COMPLIANCE",
        }

        self.assertTrue(expected_values.issubset({department.value for department in Department}))


class CompanyPackageExportsTestCase(unittest.TestCase):
    """Tests for public company package exports."""

    def test_company_package_exports_core_metadata_types(self) -> None:
        """engine.company exposes the core company metadata API."""
        self.assertIs(ExportedAgentDefinition, AgentDefinition)
        self.assertIs(ExportedCompanyRegistry, CompanyRegistry)
        self.assertIs(ExportedDepartment, Department)
        self.assertIs(EXPORTED_HELIOS_COMPANY_BLUEPRINT, HELIOS_COMPANY_BLUEPRINT)


class AgentDefinitionTestCase(unittest.TestCase):
    """Tests for AgentDefinition."""

    def test_agent_definition_stores_metadata(self) -> None:
        """AgentDefinition stores provider-neutral metadata."""
        definition = create_definition()

        self.assertEqual(definition.agent_id, "agent-1")
        self.assertEqual(definition.display_name, "Test Agent")
        self.assertIs(definition.department, Department.RESEARCH)
        self.assertEqual(definition.capability, "TREND_RESEARCH")
        self.assertEqual(definition.required_tools, ("tool",))

    def test_agent_definition_is_immutable(self) -> None:
        """AgentDefinition is immutable metadata."""
        definition = create_definition()

        with self.assertRaises(FrozenInstanceError):
            setattr(definition, "agent_id", "changed")


class CompanyRegistryTestCase(unittest.TestCase):
    """Tests for CompanyRegistry."""

    def test_register_adds_definition(self) -> None:
        """Registering a definition stores it by ID."""
        registry = CompanyRegistry()
        definition = create_definition()

        registry.register(definition)

        self.assertIs(registry.get("agent-1"), definition)

    def test_register_duplicate_id_raises_value_error(self) -> None:
        """Registering the same definition ID twice raises ValueError."""
        registry = CompanyRegistry()
        registry.register(create_definition(agent_id="agent-1"))

        with self.assertRaises(ValueError):
            registry.register(create_definition(agent_id="agent-1"))

    def test_unregister_removes_definition(self) -> None:
        """Unregistering a definition removes it from the registry."""
        registry = CompanyRegistry()
        registry.register(create_definition())

        registry.unregister("agent-1")

        self.assertFalse(registry.exists("agent-1"))

    def test_unregister_unknown_definition_raises_key_error(self) -> None:
        """Unregistering an unknown definition raises KeyError."""
        registry = CompanyRegistry()

        with self.assertRaises(KeyError):
            registry.unregister("unknown")

    def test_get_returns_registered_definition(self) -> None:
        """Getting a definition returns the registered object."""
        registry = CompanyRegistry()
        definition = create_definition()
        registry.register(definition)

        self.assertIs(registry.get("agent-1"), definition)

    def test_exists_returns_true_for_registered_definition(self) -> None:
        """Exists returns True for a registered definition."""
        registry = CompanyRegistry()
        registry.register(create_definition())

        self.assertTrue(registry.exists("agent-1"))

    def test_exists_returns_false_for_unknown_definition(self) -> None:
        """Exists returns False for an unknown definition."""
        registry = CompanyRegistry()

        self.assertFalse(registry.exists("unknown"))

    def test_all_returns_registered_definitions(self) -> None:
        """All returns definitions in registration order."""
        registry = CompanyRegistry()
        first = create_definition(agent_id="agent-1")
        second = create_definition(agent_id="agent-2")
        registry.register(first)
        registry.register(second)

        self.assertEqual(registry.all(), [first, second])

    def test_find_by_department_returns_matches(self) -> None:
        """Definitions can be searched by department."""
        registry = CompanyRegistry()
        research = create_definition(agent_id="research", department=Department.RESEARCH)
        strategy = create_definition(agent_id="strategy", department=Department.STRATEGY)
        registry.register(research)
        registry.register(strategy)

        self.assertEqual(registry.find_by_department(Department.RESEARCH), [research])

    def test_find_by_capability_returns_matches(self) -> None:
        """Definitions can be searched by capability."""
        registry = CompanyRegistry()
        trend = create_definition(agent_id="trend", capability="TREND_RESEARCH")
        audience = create_definition(agent_id="audience", capability="AUDIENCE_RESEARCH")
        registry.register(trend)
        registry.register(audience)

        self.assertEqual(registry.find_by_capability("TREND_RESEARCH"), [trend])

    def test_count_returns_number_of_definitions(self) -> None:
        """Count returns the number of registered definitions."""
        registry = CompanyRegistry()
        registry.register(create_definition(agent_id="agent-1"))
        registry.register(create_definition(agent_id="agent-2"))

        self.assertEqual(registry.count(), 2)


class HeliosCompanyBlueprintTestCase(unittest.TestCase):
    """Tests for the Helios company blueprint."""

    def test_blueprint_contains_thirty_one_agent_definitions(self) -> None:
        """The company blueprint contains the required number of definitions."""
        self.assertEqual(len(HELIOS_COMPANY_BLUEPRINT), 31)

    def test_blueprint_contains_required_agent_names(self) -> None:
        """The company blueprint contains all required agent display names."""
        expected_names = {
            "CEO",
            "System Supervisor",
            "Trend Research",
            "Audience Research",
            "Strategy",
            "Knowledge",
            "Script",
            "Hook",
            "Storyboard",
            "Creative Director",
            "Avatar",
            "Video Production",
            "Voice",
            "Music & Sound",
            "Thumbnail",
            "Caption",
            "Publishing",
            "Analytics",
            "Business Intelligence",
            "Learning",
            "Memory",
            "Experiment",
            "Report",
            "Alert",
            "Compliance",
            "Cost Manager",
            "Prompt Engineer",
            "Collaboration",
            "Content Quality",
            "Memory Optimizer",
            "Prediction",
        }

        blueprint_names = {definition.display_name for definition in HELIOS_COMPANY_BLUEPRINT}

        self.assertEqual(blueprint_names, expected_names)

    def test_blueprint_contains_business_intelligence_definition(self) -> None:
        """The blueprint contains the Business Intelligence definition."""
        definitions = {
            definition.agent_id: definition for definition in HELIOS_COMPANY_BLUEPRINT
        }

        definition = definitions["business_intelligence"]

        self.assertEqual(definition.display_name, "Business Intelligence")
        self.assertIs(definition.department, Department.ANALYTICS)
        self.assertEqual(
            definition.capability,
            AgentCapability.BUSINESS_INTELLIGENCE.value,
        )
        self.assertIn(
            "markenuebergreifende Performance analysieren",
            definition.responsibilities,
        )
        self.assertIn("Analytics-Daten", definition.inputs)
        self.assertIn("Portfolio-Auswertung", definition.outputs)

    def test_blueprint_agent_ids_are_unique(self) -> None:
        """Every blueprint definition has a unique agent ID."""
        agent_ids = [definition.agent_id for definition in HELIOS_COMPANY_BLUEPRINT]

        self.assertEqual(len(agent_ids), len(set(agent_ids)))

    def test_blueprint_definitions_are_complete(self) -> None:
        """Every blueprint definition has complete metadata."""
        for definition in HELIOS_COMPANY_BLUEPRINT:
            self.assertTrue(definition.agent_id)
            self.assertTrue(definition.display_name)
            self.assertIsInstance(definition.department, Department)
            self.assertTrue(definition.capability)
            self.assertTrue(definition.description)
            self.assertTrue(definition.responsibilities)
            self.assertTrue(definition.inputs)
            self.assertTrue(definition.outputs)
            self.assertTrue(definition.required_tools)
            self.assertTrue(definition.memory_access)
            self.assertTrue(definition.event_subscriptions)

    def test_blueprint_can_be_registered(self) -> None:
        """The blueprint can be loaded into a CompanyRegistry."""
        registry = CompanyRegistry()

        for definition in HELIOS_COMPANY_BLUEPRINT:
            registry.register(definition)

        self.assertEqual(registry.count(), 31)
        self.assertEqual(
            registry.find_by_capability("TREND_RESEARCH"),
            [registry.get("trend_research")],
        )
        self.assertIn(
            registry.get("ceo"),
            registry.find_by_department(Department.EXECUTIVE),
        )


if __name__ == "__main__":
    unittest.main()
