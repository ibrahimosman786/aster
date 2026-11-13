/** Tile office and the walk paths the floor uses.

The membership of a point is a tile inside the room that is not a wall, a desk,
or the skill board. `findPath` returns the tiles from the step after `start`
through `goal`, or null when no such walk exists. This is the same grid search
the Munder Difflin office uses.
*/

export const COLS = 22;
export const ROWS = 13;
export const TILE = 16;

export type TilePoint = { x: number; y: number };

export const DOOR: TilePoint = { x: 1, y: 6 };
export const BOARD: TilePoint = { x: 19, y: 5 };

/** Standing spots around the center table, in employee order. */
export const MEETING: TilePoint[] = [
  { x: 9, y: 6 },
  { x: 11, y: 6 },
  { x: 10, y: 5 },
  { x: 8, y: 6 },
  { x: 12, y: 6 },
  { x: 10, y: 7 },
];

export const SEATS: TilePoint[] = [
  { x: 3, y: 4 },
  { x: 8, y: 4 },
  { x: 13, y: 4 },
  { x: 3, y: 9 },
  { x: 8, y: 9 },
  { x: 13, y: 9 },
];

const WANDER: TilePoint[] = [
  { x: 6, y: 6 },
  { x: 11, y: 6 },
  { x: 16, y: 7 },
  { x: 18, y: 8 },
  { x: 5, y: 7 },
  { x: 10, y: 11 },
];

function blocked(x: number, y: number): boolean {
  for (const seat of SEATS) {
    if (y === seat.y - 1 && (x === seat.x || x === seat.x + 1)) return true;
  }
  if (x === 10 && y === 6) return true;
  if (x === 20 && y >= 2 && y <= 7) return true;
  if (x === 19 && y === 10) return true;
  return false;
}

export function isWalkable(x: number, y: number): boolean {
  if (x < 0 || y < 0 || x >= COLS || y >= ROWS) return false;
  if (x === 0 || y === 0 || x === COLS - 1 || y === ROWS - 1) {
    return x === DOOR.x && y === DOOR.y;
  }
  return !blocked(x, y);
}

export function findPath(start: TilePoint, goal: TilePoint): TilePoint[] | null {
  if (start.x === goal.x && start.y === goal.y) return [];
  if (!isWalkable(goal.x, goal.y)) return null;
  const key = (point: TilePoint) => `${point.x},${point.y}`;
  const visited = new Set<string>([key(start)]);
  const parent = new Map<string, TilePoint>();
  const queue: TilePoint[] = [start];
  const directions = [
    { x: 0, y: -1 },
    { x: 0, y: 1 },
    { x: -1, y: 0 },
    { x: 1, y: 0 },
  ];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) break;
    for (const direction of directions) {
      const next = { x: current.x + direction.x, y: current.y + direction.y };
      const nextKey = key(next);
      if (visited.has(nextKey) || !isWalkable(next.x, next.y)) continue;
      visited.add(nextKey);
      parent.set(nextKey, current);
      if (next.x === goal.x && next.y === goal.y) {
        const path: TilePoint[] = [];
        let cursor = goal;
        while (!(cursor.x === start.x && cursor.y === start.y)) {
          path.unshift(cursor);
          const previous = parent.get(key(cursor));
          if (!previous) return null;
          cursor = previous;
        }
        return path;
      }
      queue.push(next);
    }
  }
  return null;
}

export function wanderTile(index: number): TilePoint {
  return WANDER[index % WANDER.length] ?? WANDER[0];
}

export function tileOf(px: number, py: number): TilePoint {
  return { x: Math.round((px - TILE / 2) / TILE), y: Math.round((py - (TILE - 2)) / TILE) };
}

export function feetAt(tile: TilePoint): { x: number; y: number } {
  return { x: tile.x * TILE + TILE / 2, y: tile.y * TILE + TILE - 2 };
}
