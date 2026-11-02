export const MASS_ACTION_GEOS = ["PL", "CZ", "AZ", "DE"];

export type MassActionFilter = { brand: string; geo: string; include_general: boolean; site_type: "monobrand" | "general" | null };
export type MassActionSelection = { filter: MassActionFilter | null; site_ids: string[] };
