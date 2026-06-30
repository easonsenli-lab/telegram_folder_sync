import { useEffect, useRef } from 'react';

export default function EarthNetwork() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    // Particle flow configurations over the network paths
    const particles: Array<{
      x: number;
      y: number;
      targetX: number;
      targetY: number;
      progress: number;
      speed: number;
      size: number;
    }> = [];

    // Helper to generate a random flow particle
    const createParticle = () => {
      // Coordinates mapping to approximate paths on the earth background
      const startX = width * (0.4 + Math.random() * 0.2);
      const startY = height * (0.35 + Math.random() * 0.15);
      const angle = Math.random() * Math.PI * 2;
      const distance = Math.random() * 200 + 100;
      
      return {
        x: startX,
        y: startY,
        targetX: startX + Math.cos(angle) * distance,
        targetY: startY + Math.sin(angle) * distance,
        progress: 0,
        speed: Math.random() * 0.003 + 0.001,
        size: Math.random() * 1.5 + 0.8,
      };
    };

    // Initialize particles
    for (let i = 0; i < 15; i++) {
      particles.push(createParticle());
    }

    const resizeHandler = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };
    window.addEventListener('resize', resizeHandler);

    // Animation loop
    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw flowing golden light nodes on the paths
      particles.forEach((p, index) => {
        p.progress += p.speed;
        if (p.progress > 1) {
          particles[index] = createParticle();
          return;
        }

        // Quadratic bezier arc path
        const t = p.progress;
        const midX = (p.x + p.targetX) / 2;
        const midY = (p.y + p.targetY) / 2 - 30; // Curve height

        const curX = (1 - t) * (1 - t) * p.x + 2 * (1 - t) * t * midX + t * t * p.targetX;
        const curY = (1 - t) * (1 - t) * p.y + 2 * (1 - t) * t * midY + t * t * p.targetY;

        // Draw particle
        ctx.beginPath();
        ctx.arc(curX, curY, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 216, 138, ${Math.sin(t * Math.PI) * 0.65})`;
        ctx.fill();

        // Subtle glow around particle
        ctx.beginPath();
        ctx.arc(curX, curY, p.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(217, 164, 65, ${Math.sin(t * Math.PI) * 0.25})`;
        ctx.fill();
      });

      animationId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resizeHandler);
    };
  }, []);

  return (
    <div className="absolute inset-0 z-0 select-none pointer-events-none w-full h-full overflow-hidden bg-brand-dark">
      {/* 1. High-fidelity space earth background image */}
      <img
        src="assets/earth_bg.png"
        alt="RosePay India wake-up service network"
        className="w-full h-[90%] md:h-full object-cover opacity-85 object-center scale-[1.08] lg:scale-100"
      />

      {/* 2. Soft atmospheric masks to blend edge boxes */}
      <div className="absolute inset-0 bg-gradient-to-t from-brand-dark via-transparent to-brand-dark opacity-90"></div>
      <div className="absolute inset-0 bg-gradient-to-r from-brand-dark via-transparent to-brand-dark opacity-90"></div>

      {/* 3. Canvas overlay drawing light particles */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
      />
    </div>
  );
}
