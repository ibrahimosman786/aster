"use client";

import { useEffect, useRef } from "react";
import { EMPLOYEES, agentView, type AgentMode, type EmployeeId, type OfficeEvent } from "@/lib/company/office";
import { BOARD, COLS, DOOR, MEETING, ROWS, SEATS, TILE, feetAt, findPath, tileOf, wanderTile, type TilePoint } from "@/lib/company/floorMap";
import { SCENE_H, SCENE_W, sceneFrameBufs, type OfficeCharacterName } from "@/lib/company/portraitArt";

const CAST: Record<EmployeeId, OfficeCharacterName> = {
  nova: "michael",
  scout: "dwight",
  lumi: "pam",
  forge: "jim",
  pixel: "oscar",
  sage: "angela",
};

const SPEED = 42;

type Actor = {
  id: EmployeeId;
  label: string;
  cast: OfficeCharacterName;
  x: number;
  y: number;
  path: TilePoint[];
  frame: number;
  facing: "front" | "back";
  flip: boolean;
  bubble: string;
  bubbleUntil: number;
  typing: boolean;
  mode: AgentMode;
  cue: string;
  roamAt: number;
  roam: number;
};

type Envelope = { from: EmployeeId; to: EmployeeId; t: number };

type Frames = { front: HTMLCanvasElement[]; back: HTMLCanvasElement[] };

function bake(buf: Uint8ClampedArray): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = SCENE_W;
  canvas.height = SCENE_H;
  const context = canvas.getContext("2d");
  if (!context) return canvas;
  const image = context.createImageData(SCENE_W, SCENE_H);
  image.data.set(buf);
  context.putImageData(image, 0, 0);
  return canvas;
}

function listener(detail: string, speaker: EmployeeId): EmployeeId | null {
  for (const member of EMPLOYEES) {
    if (member.id === speaker) continue;
    if (detail.includes(member.name)) return member.id;
  }
  return null;
}

export type FloorPin = {
  id: EmployeeId;
  name: string;
  mode: string;
  chip: string;
  x: number;
  y: number;
};

export function OfficeFloor({
  events,
  selected,
  onSelect,
  skillKept,
  onPins,
}: {
  events: OfficeEvent[];
  selected: EmployeeId;
  onSelect: (id: EmployeeId) => void;
  skillKept: boolean;
  onPins: (pins: FloorPin[]) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const eventsRef = useRef(events);
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);
  const skillRef = useRef(skillKept);
  const onPinsRef = useRef(onPins);
  eventsRef.current = events;
  selectedRef.current = selected;
  onSelectRef.current = onSelect;
  skillRef.current = skillKept;
  onPinsRef.current = onPins;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const context = canvas.getContext("2d");
    if (!context) return undefined;
    canvas.width = COLS * TILE;
    canvas.height = ROWS * TILE;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const frames = new Map<EmployeeId, Frames>();
    for (const member of EMPLOYEES) {
      const baked = sceneFrameBufs(CAST[member.id]);
      frames.set(member.id, { front: baked.front.map(bake), back: baked.back.map(bake) });
    }
    const door = feetAt(DOOR);
    const actors: Actor[] = EMPLOYEES.map((member, index) => {
      const seat = SEATS[index] ?? DOOR;
      const home = feetAt(seat);
      return {
        id: member.id,
        label: member.name,
        cast: CAST[member.id],
        x: reduce ? home.x : door.x,
        y: reduce ? home.y : door.y,
        path: reduce ? [] : findPath(DOOR, seat) ?? [],
        frame: index,
        facing: "front",
        flip: false,
        bubble: "",
        bubbleUntil: 0,
        typing: false,
        mode: "idle",
        cue: "",
        roamAt: 0,
        roam: index,
      };
    });
    const envelopes: Envelope[] = [];
    let last = performance.now();
    let timer = 0;
    let pinKey = "";

    const go = (actor: Actor, goal: TilePoint) => {
      const start = tileOf(actor.x, actor.y);
      actor.path = findPath(start, goal) ?? [];
    };

    const deskModes: AgentMode[] = ["planning", "thinking", "working", "testing", "reviewing"];

    const follow = (actor: Actor, index: number, now: number) => {
      const view = agentView(eventsRef.current, actor.id);
      const cue = `${view.mode}|${view.action}`;
      if (cue === actor.cue) {
        if (deskModes.includes(view.mode) || view.mode === "meeting" || view.mode === "discussion") actor.bubbleUntil = now + 800;
        return;
      }
      const previous = actor.cue;
      actor.cue = cue;
      actor.mode = view.mode;
      actor.bubble = view.chip;
      actor.bubbleUntil = now + 800;
      const seat = SEATS[index] ?? DOOR;
      const talking = view.mode === "meeting" || view.mode === "discussion";
      if (talking) {
        actor.typing = false;
        go(actor, MEETING[index] ?? seat);
        const other = listener(view.action, actor.id);
        if (other && previous && view.mode === "discussion" && view.action.startsWith(`${actor.label}:`)) {
          envelopes.push({ from: actor.id, to: other, t: 0 });
        }
        return;
      }
      if (view.mode === "reviewing" && actor.id === "sage") {
        actor.typing = true;
        go(actor, BOARD);
        return;
      }
      if (deskModes.includes(view.mode)) {
        actor.typing = view.mode !== "reviewing" || actor.id === "sage";
        go(actor, seat);
        return;
      }
      actor.typing = false;
      actor.bubbleUntil = now + 1600;
    };

    const stepActor = (actor: Actor, dt: number, now: number) => {
      const goal = actor.path[0];
      if (!goal) {
        if (actor.typing) actor.frame += dt * 6;
        if (actor.roamAt === 0) actor.roamAt = now + 1600;
        const roaming = actor.mode === "idle" || actor.mode === "done" || actor.mode === "failed";
        if (roaming && !reduce && now > actor.roamAt) {
          actor.roam += 1;
          const home = SEATS[EMPLOYEES.findIndex((member) => member.id === actor.id)] ?? DOOR;
          const next = actor.roam % 2 === 0 ? wanderTile(actor.roam) : home;
          go(actor, next);
          actor.roamAt = actor.path.length === 0 ? now + 1600 : 0;
        }
        return;
      }
      const point = feetAt(goal);
      const dx = point.x - actor.x;
      const dy = point.y - actor.y;
      const distance = Math.hypot(dx, dy);
      const step = SPEED * dt;
      if (distance <= step || reduce) {
        actor.x = point.x;
        actor.y = point.y;
        actor.path.shift();
      } else {
        actor.x += (dx / distance) * step;
        actor.y += (dy / distance) * step;
      }
      if (Math.abs(dx) > Math.abs(dy)) {
        actor.facing = "front";
        actor.flip = dx < 0;
      } else {
        actor.facing = dy < 0 ? "back" : "front";
        actor.flip = false;
      }
      actor.frame += dt * 8;
    };

    const draw = (now: number) => {
      context.imageSmoothingEnabled = false;
      context.clearRect(0, 0, canvas.width, canvas.height);
      for (let y = 0; y < ROWS; y += 1) {
        for (let x = 0; x < COLS; x += 1) {
          const edge = x === 0 || y === 0 || x === COLS - 1 || y === ROWS - 1;
          const door = x === DOOR.x && y === DOOR.y;
          context.fillStyle = edge && !door ? "#8b6f47" : (x + y) % 2 === 0 ? "#e5c896" : "#c9a66b";
          context.fillRect(x * TILE, y * TILE, TILE, TILE);
        }
      }
      context.fillStyle = "#d99168";
      context.fillRect(DOOR.x * TILE, DOOR.y * TILE, TILE, TILE);
      for (const seat of SEATS) {
        context.fillStyle = "#a67c52";
        context.fillRect(seat.x * TILE, (seat.y - 1) * TILE, TILE * 2, TILE);
        context.fillStyle = "#1a1320";
        context.fillRect(seat.x * TILE + 4, (seat.y - 1) * TILE + 3, 10, 7);
      }
      const learned = skillRef.current || eventsRef.current.some((event) => event.name === "learning.version.promoted");
      context.fillStyle = learned ? "#5ca97a" : "#fff8e7";
      context.fillRect(20 * TILE, 2 * TILE, TILE, TILE * 6);
      context.fillStyle = "#4f9faf";
      context.fillRect(19 * TILE + 4, 10 * TILE + 2, 8, 10);
      context.fillStyle = "#8b6f47";
      context.fillRect(10 * TILE + 3, 6 * TILE + 4, TILE - 6, TILE - 8);

      actors.forEach((actor, index) => follow(actor, index, now));
      for (const actor of actors) stepActor(actor, Math.min(0.05, (now - last) / 1000), now);
      last = now;

      for (const envelope of envelopes) envelope.t += 0.02;
      for (let index = envelopes.length - 1; index >= 0; index -= 1) {
        const envelope = envelopes[index];
        if (!envelope || envelope.t >= 1) {
          envelopes.splice(index, 1);
          continue;
        }
        const from = actors.find((actor) => actor.id === envelope.from);
        const to = actors.find((actor) => actor.id === envelope.to);
        if (!from || !to) continue;
        const x = from.x + (to.x - from.x) * envelope.t;
        const y = from.y - 28 + (to.y - from.y) * envelope.t;
        context.fillStyle = "#f4efe4";
        context.fillRect(x, y, 6, 4);
        context.fillStyle = "#8a3b32";
        context.fillRect(x, y, 6, 1);
      }

      const ordered = [...actors].sort((a, b) => a.y - b.y);
      for (const actor of ordered) {
        const sheet = frames.get(actor.id);
        const row = actor.facing === "back" ? sheet?.back : sheet?.front;
        const sprite = row?.[Math.floor(actor.frame) % (row.length || 1)];
        const dx = Math.round(actor.x - SCENE_W / 2);
        const dy = Math.round(actor.y - SCENE_H);
        if (actor.id === selectedRef.current) {
          context.fillStyle = "rgba(244,239,228,0.35)";
          context.fillRect(dx + 2, actor.y - 2, SCENE_W - 4, 3);
        }
        if (sprite) {
          context.save();
          if (actor.flip) {
            context.translate(dx + SCENE_W, dy);
            context.scale(-1, 1);
            context.drawImage(sprite, 0, 0);
          } else {
            context.drawImage(sprite, dx, dy);
          }
          context.restore();
        }
        if (actor.typing) {
          const seat = SEATS[EMPLOYEES.findIndex((member) => member.id === actor.id)];
          if (seat && Math.abs(actor.x - feetAt(seat).x) < 4) {
            context.fillStyle = "#5ca97a";
            context.fillRect(seat.x * TILE + 6, (seat.y - 1) * TILE + 5, 6, 3);
          }
        }
      }
      const pins = actors.map((actor) => ({
        id: actor.id,
        name: actor.label,
        mode: actor.mode,
        chip: now < actor.bubbleUntil ? actor.bubble : "",
        x: actor.x / canvas.width,
        y: actor.y / canvas.height,
      }));
      const nextKey = pins.map((pin) => `${pin.id}:${pin.x.toFixed(3)}:${pin.y.toFixed(3)}:${pin.chip}:${pin.mode}`).join("|");
      if (nextKey !== pinKey) {
        pinKey = nextKey;
        onPinsRef.current(pins);
      }
    };

    const tick = (now: number) => {
      draw(now);
      timer = window.requestAnimationFrame(tick);
    };
    timer = window.requestAnimationFrame(tick);

    const onClick = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
      const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
      let closest: Actor | null = null;
      let best = 28;
      for (const actor of actors) {
        const distance = Math.hypot(actor.x - x, actor.y - 16 - y);
        if (distance < best) {
          best = distance;
          closest = actor;
        }
      }
      if (closest) onSelectRef.current(closest.id);
    };
    canvas.addEventListener("click", onClick);
    return () => {
      window.cancelAnimationFrame(timer);
      canvas.removeEventListener("click", onClick);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-label="Office floor. Employees walk between desks while they work."
      className="office-floor"
    />
  );
}
