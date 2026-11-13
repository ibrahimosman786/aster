import assert from "node:assert/strict";
import test from "node:test";
import { DOOR, MEETING, SEATS, findPath, isWalkable } from "./floorMap.ts";

test("every desk is reachable from the office door", () => {
  for (const seat of SEATS) {
    assert.equal(isWalkable(seat.x, seat.y), true);
    const path = findPath(DOOR, seat);
    assert.ok(path);
    assert.ok(path.length > 2);
    assert.equal(path[path.length - 1].x, seat.x);
    assert.equal(path[path.length - 1].y, seat.y);
  }
  for (const spot of MEETING) {
    assert.equal(isWalkable(spot.x, spot.y), true);
    assert.ok(findPath(DOOR, spot));
  }
  assert.equal(isWalkable(10, 6), false);
});
