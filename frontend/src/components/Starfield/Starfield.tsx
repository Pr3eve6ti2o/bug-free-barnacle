import { FC, useEffect, useRef } from 'react';

/** Subtle animated starfield: twinkling stars drifting slowly. Pure canvas, cheap. */
export const Starfield: FC = () => {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = 0, h = 0, raf = 0;
    const DPR = Math.min(2, window.devicePixelRatio || 1);
    interface Star { x: number; y: number; r: number; base: number; speed: number; phase: number; drift: number }
    let stars: Star[] = [];

    const resize = () => {
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * DPR; canvas.height = h * DPR;
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      const count = Math.min(140, Math.floor((w * h) / 12000));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 0.4 + Math.random() * 1.3,
        base: 0.25 + Math.random() * 0.55,
        speed: 0.4 + Math.random() * 1.2,
        phase: Math.random() * Math.PI * 2,
        drift: 2 + Math.random() * 8,
      }));
    };

    let t = 0;
    let last = performance.now();
    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now; t += dt;
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        const tw = s.base * (0.6 + 0.4 * Math.sin(s.phase + t * s.speed));
        s.y -= s.drift * dt;
        if (s.y < -4) { s.y = h + 4; s.x = Math.random() * w; }
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(235, 240, 255, ${tw.toFixed(3)})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(frame);
    };

    resize();
    window.addEventListener('resize', resize);
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      style={{
        position: 'fixed', inset: 0, zIndex: 0,
        pointerEvents: 'none', opacity: 0.85,
      }}
    />
  );
};
