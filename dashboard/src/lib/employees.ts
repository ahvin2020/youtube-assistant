import { Employee, EmployeeStatus, Domain, Project } from "./types";
import employeeData from "../data/employees.json";

interface RawEmployee {
  id: string;
  name: string;
  title: string;
  avatar: string;
  domains: string[];
  personality: string;
  skills: string[];
  color: string;
}

export function getEmployees(projects: Project[]): Employee[] {
  const activeProjects = projects.filter(
    (p) => p.state?.phase && p.state.phase !== "complete"
  );

  return (employeeData as RawEmployee[]).map((raw) => {
    // Find active project in this employee's domains
    const assignment = activeProjects.find((p) =>
      raw.domains.includes(p.domain)
    );

    const status: EmployeeStatus = assignment ? "busy" : "idle";
    const currentAssignment = assignment
      ? `${assignment.displayName} (${assignment.currentPhase})`
      : null;

    // Count completed projects
    const projectsCompleted = projects.filter(
      (p) =>
        raw.domains.includes(p.domain) &&
        p.state?.phase === "complete"
    ).length;

    return {
      id: raw.id,
      name: raw.name,
      title: raw.title,
      avatar: raw.avatar,
      domains: raw.domains as Domain[],
      personality: raw.personality,
      skills: raw.skills,
      color: raw.color,
      status,
      currentAssignment,
      projectsCompleted,
    };
  });
}
