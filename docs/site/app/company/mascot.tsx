"use client";

import { useEffect, useRef } from "react";
import { SCENE_H, SCENE_W, sceneFrameBufs, type OfficeCharacterName } from "@/lib/company/portraitArt";

export function OfficeMascot({ name, moving }: { name: OfficeCharacterName; moving: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const frames = sceneFrameBufs(name).front;
    const scale = 4;
    canvas.width = SCENE_W * scale;
    canvas.height = SCENE_H * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let frame = 0;
    const draw = (index: number) => {
      const stage = document.createElement("canvas");
      stage.width = SCENE_W;
      stage.height = SCENE_H;
      const stageCtx = stage.getContext("2d");
      if (!stageCtx) return;
      const image = stageCtx.createImageData(SCENE_W, SCENE_H);
      image.data.set(frames[index] ?? frames[0]);
      stageCtx.putImageData(image, 0, 0);
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(stage, 0, 0, SCENE_W, SCENE_H, 0, 0, canvas.width, canvas.height);
    };
    draw(0);
    if (!moving) return undefined;
    const timer = window.setInterval(() => {
      frame = (frame + 1) % frames.length;
      draw(frame);
    }, 180);
    return () => window.clearInterval(timer);
  }, [moving, name]);

  return <canvas ref={ref} width={72} height={128} aria-hidden="true" style={{ width: 72, height: 128, imageRendering: "pixelated" }} />;
}
