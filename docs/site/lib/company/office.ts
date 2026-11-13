/** A company run: six employees, real checks, and a skill kept only after those checks pass. */

export type EmployeeId = "nova" | "scout" | "lumi" | "forge" | "pixel" | "sage";

export type Employee = {
  id: EmployeeId;
  name: string;
  title: string;
  responsibility: string;
};

export type AgentMode =
  | "idle"
  | "planning"
  | "thinking"
  | "working"
  | "meeting"
  | "discussion"
  | "testing"
  | "reviewing"
  | "done"
  | "blocked"
  | "failed";

export type AgentTool = "think" | "read" | "write" | "edit" | "test" | "handoff";

export type OfficeEvent = {
  name: "task.started" | "task.completed" | "task.failed" | "test.completed" | "handoff.created" | "artifact.created" | "learning.version.promoted";
  employee: EmployeeId;
  task: string;
  detail: string;
  mode: AgentMode;
  tool: AgentTool;
  /** The file or check this step opens. */
  target: string;
  /** Others who are in this moment. A meeting includes the whole floor. */
  with?: EmployeeId[];
};

export type TraceStep = {
  tool: AgentTool;
  target: string;
  detail: string;
};

export type PlanStep = {
  id: string;
  owner: EmployeeId;
  label: string;
  state: "done" | "now" | "waiting" | "failed" | "skipped";
};

export type AgentView = {
  mode: AgentMode;
  action: string;
  /** Short floor label, such as "write plan.md". */
  chip: string;
  thought: string;
  plan: PlanStep[];
  trace: TraceStep[];
  discussion: { speaker: EmployeeId; line: string }[];
};

export const PLAN: { id: string; owner: EmployeeId; label: string }[] = [
  { id: "plan", owner: "nova", label: "Turn the request into a plan" },
  { id: "meeting", owner: "nova", label: "Discuss the request" },
  { id: "research", owner: "scout", label: "Write notes from the request" },
  { id: "layout", owner: "lumi", label: "Describe the result" },
  { id: "write-tests", owner: "pixel", label: "Write the check before the build" },
  { id: "implement", owner: "forge", label: "Build the files" },
  { id: "test", owner: "pixel", label: "Run the check" },
  { id: "repair", owner: "forge", label: "Fix the build once if the check fails" },
  { id: "review", owner: "sage", label: "Keep a lesson only if the check passes" },
];

const FLOOR: EmployeeId[] = ["nova", "scout", "lumi", "forge", "pixel", "sage"];

export type Skill = {
  id: string;
  procedure: string;
  acceptance: string;
  holdout: string;
};

export type OfficeRun = {
  brief: string;
  events: OfficeEvent[];
  files: Record<string, string>;
  passed: boolean;
  blocked: boolean;
  skill: Skill | null;
};

export const EMPLOYEES: Employee[] = [
  { id: "nova", name: "Nova", title: "Lead", responsibility: "Turns your request into a plan and runs the meeting." },
  { id: "scout", name: "Scout", title: "Research", responsibility: "Writes down only what you asked, so the team does not invent requirements." },
  { id: "lumi", name: "Lumi", title: "Design", responsibility: "Describes what the result should look like before anyone builds it." },
  { id: "forge", name: "Forge", title: "Build", responsibility: "Writes the files. Forge does not edit the check." },
  { id: "pixel", name: "Pixel", title: "Check", responsibility: "Writes a test and runs it. A lesson is kept only if that test passes." },
  { id: "sage", name: "Sage", title: "Review", responsibility: "Records the lesson after the test passes. Sage does not keep it because it sounds good." },
];

const SKILL_PROCEDURE = "refuse a slot that is already booked";

export function runCompany(brief: string, accepted: Skill | null): OfficeRun {
  const text = brief.trim();
  const events: OfficeEvent[] = [];
  const files: Record<string, string> = {};
  if (!text) {
    record(events, "nova", "task.failed", "brief", "blocked: the brief is empty", "blocked", "think", "brief");
    return { brief: text, events, files, passed: false, blocked: true, skill: null };
  }

  files["brief"] = text;
  files["plan.md"] = `# Plan\n\nBrief: ${text}\n\n1. Write the checks from the brief.\n2. Meet and assign the steps.\n3. Record only the brief.\n4. Describe one booking screen.\n5. Lock the tests before the code.\n6. Build the desk.\n7. Run the acceptance check.\n8. Repair once if it fails.\n9. Run a separate fixture.\n10. Keep a skill only when both checks pass.\n`;
  record(events, "nova", "task.started", "plan", "Nova is planning the job from the brief.", "planning", "think", "plan.md");
  record(events, "nova", "task.started", "plan", "Nova is thinking: a slot can be booked once. That check comes before any code.", "thinking", "think", "plan.md");
  record(events, "nova", "artifact.created", "plan", "Wrote the plan.", "planning", "write", "plan.md");
  record(events, "nova", "task.completed", "plan", "The plan is ready. A slot can be booked once.", "planning", "think", "plan.md");
  record(events, "nova", "handoff.created", "meeting", "Nova called the planning meeting.", "meeting", "handoff", "meeting", FLOOR);
  record(events, "nova", "handoff.created", "meeting", "Nova: Scout copies the brief. Lumi draws one screen. Pixel locks the tests. Forge writes the desk. Sage keeps a skill only after both checks.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "scout", "handoff.created", "meeting", "Scout: I will copy only lines from the brief.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "lumi", "handoff.created", "meeting", "Lumi: one screen lists open slots. A second booking of the same slot is refused.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "pixel", "handoff.created", "meeting", "Pixel: I will lock the tests before Forge writes code.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "forge", "handoff.created", "meeting", "Forge: I will not edit the tests.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "sage", "handoff.created", "meeting", "Sage: I keep a skill only when the acceptance check and the separate fixture both pass.", "discussion", "handoff", "meeting", FLOOR);
  record(events, "nova", "task.completed", "meeting", "The meeting ended. Each person has a step.", "done", "handoff", "meeting", FLOOR);

  const requirements = `# Requirements\n\n${text}\n\n- A slot can be booked once.\n`;
  files["requirements.md"] = requirements;
  record(events, "nova", "task.started", "requirements", "Nova is writing the acceptance checks.", "thinking", "think", "requirements.md");
  record(events, "nova", "artifact.created", "requirements", "Wrote the acceptance checks.", "working", "write", "requirements.md");
  record(events, "nova", "task.completed", "requirements", "requirements.md says a slot can be booked once.", "working", "write", "requirements.md");
  record(events, "nova", "handoff.created", "requirements", "Nova handed requirements.md to Scout.", "discussion", "handoff", "requirements.md", ["nova", "scout"]);

  const research = `# Research\n\nCopied from the brief. No outside source.\n\n${text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `- ${line}`)
    .join("\n")}\n`;
  files["research.md"] = research;
  record(events, "scout", "task.started", "research", "Scout is reading the brief and nothing else.", "thinking", "read", "brief");
  record(events, "scout", "task.completed", "research", "Scout kept only lines from the brief.", "working", "think", "research.md");
  record(events, "scout", "artifact.created", "research", "Wrote the research notes.", "working", "write", "research.md");
  record(events, "scout", "handoff.created", "research", "Scout handed research.md to Lumi.", "discussion", "handoff", "research.md", ["scout", "lumi"]);

  files["layout.md"] = `# Layout\n\nOne screen lists open slots. Booking the same slot twice is refused.\n\nBrief: ${text}\n`;
  record(events, "lumi", "task.started", "layout", "Lumi is thinking about the one screen the brief needs.", "thinking", "think", "layout.md");
  record(events, "lumi", "task.completed", "layout", "Lumi described the booking screen.", "working", "think", "layout.md");
  record(events, "lumi", "artifact.created", "layout", "Wrote the screen layout.", "working", "write", "layout.md");
  record(events, "lumi", "handoff.created", "layout", "Lumi handed layout.md to Forge.", "discussion", "handoff", "layout.md", ["lumi", "forge"]);

  const acceptance = acceptanceSource();
  const holdout = holdoutSource();
  files["test_booking.js"] = acceptance;
  files["holdout_booking.js"] = holdout;
  record(events, "pixel", "task.started", "write-tests", "Pixel is writing the checks before any booking code exists.", "thinking", "think", "test_booking.js");
  record(events, "pixel", "artifact.created", "write-tests", "Wrote the acceptance check.", "working", "write", "test_booking.js");
  record(events, "pixel", "artifact.created", "write-tests", "Wrote the separate fixture.", "working", "write", "holdout_booking.js");
  record(events, "pixel", "task.completed", "write-tests", "Pixel locked the tests. Forge cannot change them.", "working", "write", "test_booking.js");

  const usingSkill = accepted?.procedure === SKILL_PROCEDURE;
  let program = bookingsSource(usingSkill);
  files["booking.js"] = program;
  record(events, "forge", "task.started", "implement", usingSkill ? "Forge is thinking about the accepted skill." : "Forge is thinking about a first booking desk.", "thinking", "think", "booking.js");
  record(events, "forge", "task.started", "implement", usingSkill ? "Forge is using the accepted skill." : "Forge is writing the first booking desk.", "working", "write", "booking.js");
  record(events, "forge", "artifact.created", "implement", "Wrote the first booking desk.", "working", "write", "booking.js");
  record(events, "forge", "task.completed", "implement", "booking.js is ready for Pixel.", "working", "write", "booking.js");

  const first = runAcceptance(bookings(usingSkill));
  record(events, "pixel", "task.started", "test", "Pixel is running the acceptance check.", "testing", "test", "acceptance");
  record(events, "pixel", "test.completed", "test", first.log, "testing", "test", "acceptance");
  if (!first.passed) {
    record(events, "pixel", "task.failed", "test", "The acceptance check failed.", "testing", "test", "acceptance");
    record(events, "pixel", "handoff.created", "test", "Pixel: the acceptance check failed. A duplicate booking must be refused. The test file stays locked.", "discussion", "handoff", "acceptance", ["pixel", "forge"]);
    record(events, "forge", "handoff.created", "test", "Forge: I heard the failure. I will not edit the tests.", "discussion", "handoff", "acceptance", ["pixel", "forge"]);
    const proposed = proposeSkill(first.log);
    if (!proposed) {
      record(events, "sage", "task.failed", "review", "Sage found no procedure in the test failure.", "reviewing", "think", "review");
      return { brief: text, events, files, passed: false, blocked: false, skill: null };
    }
    program = bookingsSource(true);
    files["booking.js"] = program;
    record(events, "forge", "task.started", "repair", `Forge is thinking. The procedure is: ${proposed}.`, "thinking", "think", "booking.js");
    record(events, "forge", "artifact.created", "repair", "Edited booking.js. The tests were not touched.", "working", "edit", "booking.js");
    record(events, "forge", "task.completed", "repair", "Forge repaired booking.js without editing the tests.", "working", "edit", "booking.js");
    const second = runAcceptance(bookings(true));
    record(events, "pixel", "task.started", "retest", "Pixel is running the acceptance check again.", "testing", "test", "acceptance");
    record(events, "pixel", "test.completed", "retest", second.log, "testing", "test", "acceptance");
    if (!second.passed) {
      record(events, "pixel", "task.failed", "retest", "The repair still failed the acceptance check.", "testing", "test", "acceptance");
      record(events, "sage", "task.failed", "review", second.log, "reviewing", "test", "acceptance");
      return { brief: text, events, files, passed: false, blocked: false, skill: null };
    }
    record(events, "pixel", "task.completed", "retest", "The acceptance check passed after the repair.", "testing", "test", "acceptance");
    const held = runHoldout(bookings(true));
    record(events, "pixel", "task.started", "holdout", "Pixel is running the separate fixture.", "testing", "test", "holdout");
    record(events, "pixel", "test.completed", "holdout", held.log, "testing", "test", "holdout");
    record(events, "pixel", held.passed ? "task.completed" : "task.failed", "holdout", held.passed ? "Pixel finished the separate fixture." : "Pixel recorded the separate fixture failure.", "testing", "test", "holdout");
    if (!held.passed || files["test_booking.js"] !== acceptance || files["holdout_booking.js"] !== holdout) {
      record(events, "sage", "task.failed", "review", "The separate fixture failed, so no skill was kept.", "reviewing", "test", "holdout");
      return { brief: text, events, files, passed: false, blocked: false, skill: null };
    }
    const skill: Skill = { id: "refuse-duplicate", procedure: proposed, acceptance: second.log, holdout: held.log };
    files["skill.md"] = skillFile(skill);
    record(events, "sage", "task.started", "review", "Sage is reviewing both check results.", "reviewing", "think", "skill.md");
    record(events, "sage", "learning.version.promoted", "skill", "Sage promoted refuse-duplicate into the Aster learning record.", "reviewing", "write", "skill.md");
    record(events, "sage", "artifact.created", "review", "Wrote the skill.", "reviewing", "write", "skill.md");
    record(events, "sage", "task.completed", "review", "Sage kept the skill because both checks passed.", "done", "write", "skill.md");
    return { brief: text, events, files, passed: true, blocked: false, skill };
  }

  const held = runHoldout(bookings(true));
  record(events, "pixel", "task.started", "holdout", "Pixel is running the separate fixture.", "testing", "test", "holdout");
  record(events, "pixel", "test.completed", "holdout", held.log, "testing", "test", "holdout");
  record(events, "pixel", held.passed ? "task.completed" : "task.failed", "holdout", held.passed ? "Pixel finished the separate fixture." : "Pixel recorded the separate fixture failure.", "testing", "test", "holdout");
  record(events, "sage", "task.started", "review", "Sage is reviewing the separate fixture.", "reviewing", "think", "skill.md");
  record(events, "sage", held.passed ? "task.completed" : "task.failed", "review", held.passed ? "The existing skill still passes the separate fixture." : "The existing skill failed the separate fixture.", held.passed ? "done" : "failed", "test", "holdout");
  return { brief: text, events, files, passed: held.passed, blocked: false, skill: held.passed ? accepted : null };
}

export function bookings(refuseDuplicate: boolean): { book(slot: string): boolean } {
  const taken = new Set<string>();
  return {
    book(slot: string) {
      if (refuseDuplicate && taken.has(slot)) return false;
      taken.add(slot);
      return true;
    },
  };
}

export function runAcceptance(desk: { book(slot: string): boolean }): { passed: boolean; log: string } {
  const first = desk.book("2026-11-10T10:00");
  const second = desk.book("2026-11-10T10:00");
  const passed = first === true && second === false;
  const log = passed
    ? "acceptance passed 1 of 1. A duplicate booking was refused."
    : "acceptance failed 0 of 1. A duplicate booking must be refused.";
  return { passed, log };
}

export function runHoldout(desk: { book(slot: string): boolean }): { passed: boolean; log: string } {
  const morning = desk.book("morning");
  const afternoon = desk.book("afternoon");
  const again = desk.book("morning");
  const passed = morning === true && afternoon === true && again === false;
  const log = passed
    ? "holdout passed 1 of 1. A second slot stayed free and the first slot was refused."
    : "holdout failed 0 of 1. The separate fixture did not pass.";
  return { passed, log };
}

export function proposeSkill(log: string): string | null {
  if (!log.includes("duplicate booking must be refused")) return null;
  return SKILL_PROCEDURE;
}

function record(
  events: OfficeEvent[],
  employee: EmployeeId,
  name: OfficeEvent["name"],
  task: string,
  detail: string,
  mode: AgentMode,
  tool: AgentTool,
  target: string,
  withIds?: EmployeeId[],
): void {
  events.push({ name, employee, task, detail, mode, tool, target, with: withIds });
}

function applies(event: OfficeEvent, employee: EmployeeId): boolean {
  return event.employee === employee || (event.with?.includes(employee) ?? false);
}

function stepState(events: OfficeEvent[], id: string, index: number): PlanStep["state"] {
  const related = events.filter((event) => event.task === id || (id === "review" && event.task === "skill"));
  const completed = related.some((event) => event.name === "task.completed" || event.name === "learning.version.promoted");
  const failed = related.some((event) => event.name === "task.failed");
  const started = related.length > 0;
  if (completed) return "done";
  if (failed) return "failed";
  if (started) return "now";
  const laterStarted = PLAN.slice(index + 1).some((step) => events.some((event) => event.task === step.id || (step.id === "review" && event.task === "skill")));
  if (laterStarted) return "skipped";
  return "waiting";
}

/** What one employee is doing in the events seen so far. */
export function agentView(events: OfficeEvent[], employee: EmployeeId): AgentView {
  let mode: AgentMode = "idle";
  let action = "Idle. No task has been recorded.";
  let chip = "";
  let thought = "";
  const discussion: AgentView["discussion"] = [];
  const trace: TraceStep[] = [];
  for (const event of events) {
    if (event.mode === "meeting" || event.mode === "discussion") {
      discussion.push({ speaker: event.employee, line: event.detail });
    }
    if (event.employee === employee && event.mode === "thinking") thought = event.detail;
    if (event.employee === employee) trace.push({ tool: event.tool, target: event.target, detail: event.detail });
    if (!applies(event, employee)) continue;
    mode = event.mode;
    action = event.detail;
    if (event.employee === employee) chip = `${event.tool} ${event.target}`;
  }
  return {
    mode,
    action,
    chip,
    thought,
    plan: PLAN.map((step, index) => ({ ...step, state: stepState(events, step.id, index) })),
    trace,
    discussion,
  };
}

export function employeeState(events: OfficeEvent[], employee: EmployeeId): string {
  let state = "idle";
  for (const event of events) {
    if (event.employee !== employee) continue;
    if (event.name === "task.failed" && event.detail.toLowerCase().includes("blocked")) state = "blocked";
    else if (event.name === "task.failed") state = "failed";
    else if (event.name === "test.completed") state = "testing";
    else if (event.name === "task.started") state = "working";
    else if (event.name === "task.completed") state = "done";
  }
  return state;
}

function bookingsSource(refuseDuplicate: boolean): string {
  return refuseDuplicate
    ? "class Bookings {\n  book(slot) {\n    if (this.taken.has(slot)) return false;\n    this.taken.add(slot);\n    return true;\n  }\n  constructor() { this.taken = new Set(); }\n}\n"
    : "class Bookings {\n  book() { return true; }\n}\n";
}

function acceptanceSource(): string {
  return "check that 2026-11-10T10:00 can be booked once and a duplicate booking must be refused\n";
}

function holdoutSource(): string {
  return "check that morning and afternoon can both be booked, then morning is refused\n";
}

function skillFile(skill: Skill): string {
  return `# Refuse a duplicate booking\n\nProcedure: ${skill.procedure}.\n\nAcceptance: ${skill.acceptance}\n\nHoldout: ${skill.holdout}\n`;
}
