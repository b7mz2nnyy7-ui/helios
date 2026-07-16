export interface AgentCatalogEntry {
  name: string;
  area: string;
  status: "Configured";
  capability: string;
}

export const agentCatalog: readonly AgentCatalogEntry[] = [
  { name: "Atlas", area: "Research", status: "Configured", capability: "TREND_RESEARCH" },
  { name: "Mira", area: "Research", status: "Configured", capability: "AUDIENCE_RESEARCH" },
  { name: "Sage", area: "Knowledge", status: "Configured", capability: "KNOWLEDGE" },
  { name: "Nova", area: "Strategy", status: "Configured", capability: "STRATEGY" },
  { name: "Orion", area: "Writing", status: "Configured", capability: "SCRIPT" },
  { name: "Apollo", area: "Writing", status: "Configured", capability: "HOOK" },
  { name: "Lumen", area: "Creative", status: "Configured", capability: "STORYBOARD" },
  { name: "Aether", area: "Creative", status: "Configured", capability: "CREATIVE_DIRECTION" },
  { name: "Echo", area: "Production", status: "Configured", capability: "AVATAR" },
  { name: "Vox", area: "Production", status: "Configured", capability: "VOICE" },
  { name: "Pulse", area: "Production", status: "Configured", capability: "MUSIC" },
  { name: "Forge", area: "Production", status: "Configured", capability: "VIDEO_PRODUCTION" },
  { name: "Insight", area: "Analytics", status: "Configured", capability: "ANALYTICS" },
  { name: "Mentor", area: "Optimization", status: "Configured", capability: "LEARNING" },
  { name: "Oracle", area: "Strategy", status: "Configured", capability: "PREDICTION" },
  { name: "Athena", area: "Analytics", status: "Configured", capability: "BUSINESS_INTELLIGENCE" },
  { name: "Helios", area: "Executive", status: "Configured", capability: "CEO" },
];
