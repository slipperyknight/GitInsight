"use client";

// Dependency-free "ink" trail cursor. A canvas that draws a tapering, fading stroke following
// the pointer with eased lag — feels like wet ink. Pure requestAnimationFrame + 2D canvas, no
// libraries. Disabled for touch devices and when the user prefers reduced motion.

import { useEffect, useRef } from "react";

export function InkCursor() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (reduce || !fine) return; // accessibility / touch — render nothing

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const pen = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const target = { ...pen };
    let moved = false;

    type Pt = { x: number; y: number; life: number };
    const trail: Pt[] = [];
    const MAX = 24;
    const ACCENT = "37, 99, 235"; // blue-600

    const onMove = (e: MouseEvent) => {
      target.x = e.clientX;
      target.y = e.clientY;
      moved = true;
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    let raf = 0;
    const loop = () => {
      // eased follow → fluid lag behind the real pointer
      pen.x += (target.x - pen.x) * 0.2;
      pen.y += (target.y - pen.y) * 0.2;

      if (moved) {
        trail.push({ x: pen.x, y: pen.y, life: 1 });
        if (trail.length > MAX) trail.shift();
      }
      for (const p of trail) p.life *= 0.9;
      while (trail.length && trail[0].life < 0.05) trail.shift();

      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (let i = 1; i < trail.length; i++) {
        const a = trail[i - 1];
        const b = trail[i];
        const t = i / trail.length; // tail (0) → head (1)
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.lineWidth = 1.5 + t * 7; // thin tail, thick head
        ctx.strokeStyle = `rgba(${ACCENT}, ${0.55 * b.life})`;
        ctx.stroke();
      }
      if (trail.length) {
        const h = trail[trail.length - 1];
        ctx.beginPath();
        ctx.fillStyle = `rgba(${ACCENT}, 0.95)`;
        ctx.arc(h.x, h.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[60] hidden md:block"
    />
  );
}
