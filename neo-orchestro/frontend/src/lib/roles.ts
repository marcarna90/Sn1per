import type { Role } from "../api/types";

const RANK: Record<Role, number> = { viewer: 1, analyst: 2, admin: 3 };

/** True when `role` has at least the privileges of `minimum` (the server enforces it too). */
export const atLeast = (role: Role, minimum: Role): boolean => RANK[role] >= RANK[minimum];

export const ROLE_LABEL: Record<Role, string> = {
  viewer: "Lecteur",
  analyst: "Analyste",
  admin: "Administrateur",
};
