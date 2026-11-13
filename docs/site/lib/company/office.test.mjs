import assert from "node:assert/strict";
import test from "node:test";
import { agentView, employeeState, proposeSkill, runAcceptance, runCompany, runHoldout, bookings } from "./office.ts";

test("the first company run fails, repairs, and keeps a skill after the holdout", () => {
  const run = runCompany("Build a booking website for my photography business.", null);
  assert.equal(run.passed, true);
  assert.equal(run.files["test_booking.js"], run.files["test_booking.js"]);
  assert.match(run.files["booking.js"], /taken/);
  assert.equal(run.skill?.procedure, "refuse a slot that is already booked");
  assert.match(run.skill?.acceptance ?? "", /passed 1 of 1/);
  assert.match(run.skill?.holdout ?? "", /passed 1 of 1/);
  const learned = runCompany("Build a booking website.", run.skill);
  assert.equal(learned.events.some((event) => event.task === "repair"), false);
  assert.equal(learned.passed, true);
  const duringTest = run.events.slice(0, run.events.findIndex((event) => event.name === "test.completed") + 1);
  assert.equal(employeeState(duringTest, "pixel"), "testing");
  const planned = run.events.slice(0, run.events.findIndex((event) => event.task === "plan" && event.name === "task.completed") + 1);
  const nova = agentView(planned, "nova");
  assert.equal(nova.mode, "planning");
  assert.equal(nova.plan.find((step) => step.id === "plan").state, "done");
  assert.match(nova.thought, /a slot can be booked once/);
  const meeting = run.events.slice(0, run.events.findIndex((event) => event.employee === "sage" && event.mode === "discussion") + 1);
  assert.equal(agentView(meeting, "forge").mode, "discussion");
  assert.ok(agentView(meeting, "forge").discussion.length >= 4);
  const thinking = run.events.find((event) => event.task === "repair" && event.mode === "thinking");
  assert.match(thinking.detail, /refuse a slot that is already booked/);
  const failedAt = run.events.findIndex((event) => event.name === "task.failed" && event.task === "test");
  const edits = run.events.filter((event) => event.tool === "edit" && event.target === "booking.js");
  assert.ok(edits.length >= 1);
  assert.ok(run.events.findIndex((event) => event.tool === "edit" && event.target === "booking.js") > failedAt);
  assert.ok(run.events.findIndex((event) => event.tool === "write" && event.target === "booking.js") < failedAt);
  assert.equal(learned.events.some((event) => event.tool === "edit"), false);
  assert.ok(agentView(run.events, "forge").trace.some((step) => step.tool === "edit" && step.target === "booking.js"));
});

test("a duplicate is refused only after the skill exists", () => {
  assert.equal(runAcceptance(bookings(false)).passed, false);
  assert.equal(runHoldout(bookings(true)).passed, true);
  assert.equal(proposeSkill("acceptance failed. A duplicate booking must be refused."), "refuse a slot that is already booked");
  assert.equal(proposeSkill("something else"), null);
});
