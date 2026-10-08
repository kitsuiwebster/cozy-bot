import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild } from '@angular/core';

interface Drop {
  x: number;
  y: number;
  r: number;
  momentum: number;
  momentumX: number;
  spreadX: number;
  spreadY: number;
  lastTrailY: number;
  nextTrailGap: number;
  shrink: number;
  killed: boolean;
  friction: number; // how fast a sliding drop is caught again (lower = shorter runs)
  grip: number; // how readily a heavy drop lets go of the glass
}

interface Streak {
  x: number;
  y: number;
  length: number;
  speed: number;
  alpha: number;
  width: number;
}

// Tuning. Radii are in CSS pixels.
const MIN_R = 2;
const MAX_R = 17;
const SLIDE_R = 8; // drops smaller than this stay stuck to the glass
const MAX_DROPS = 150;
const SPAWN_PER_FRAME = 0.4;
const MIST_PER_FRAME = 4;
const MIST_FADE_EVERY = 45; // frames
const REFRACTION = 2.6; // how much of the scene each drop "sees", relative to its size
const STATIC_WARMUP_FRAMES = 420;
const SLOW_FRAME_MS = 30;
// Distant rain behind the pane: streaks per screen pixel, and the slant
// (horizontal px per vertical px) the wind gives them.
const STREAK_DENSITY = 1 / 9000;
const WIND = 0.12;

// Window-pane background shared by every page: a dark night with faint, distant
// rain behind the glass, and water drops on the pane that cling, grow, merge
// and slide down in irregular bursts (some race down, most stop short),
// leaving trails and wiping the mist. Each drop refracts an inverted view of
// the scene behind it, like a real water lens. Touch
// devices and reduced-motion users get a single still frame; on desktop the
// animation lightens itself, then freezes, if it cannot hold a smooth framerate.
@Component({
  selector: 'app-rain-glass',
  standalone: true,
  template: `<canvas #scene></canvas><canvas #glass></canvas>`,
  styles: [`
    :host {
      position: fixed;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      overflow: hidden;
    }
    canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }
  `],
})
export class RainGlassComponent implements AfterViewInit, OnDestroy {
  @ViewChild('scene', { static: true }) private sceneRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('glass', { static: true }) private glassRef!: ElementRef<HTMLCanvasElement>;

  private width = 0;
  private height = 0;
  private dpr = 1;
  private drops: Drop[] = [];
  private frame = 0;
  private rafId = 0;
  private lastTime = 0;
  private slowFrames = 0;
  private maxDrops = MAX_DROPS;
  private animated = false;
  private resizeTimer: ReturnType<typeof setTimeout> | undefined;

  private glassCtx!: CanvasRenderingContext2D;
  private mist!: HTMLCanvasElement;
  private mistCtx!: CanvasRenderingContext2D;
  private refractSource!: HTMLCanvasElement; // the scene, flipped on both axes
  private dropSprite!: HTMLCanvasElement; // rim shading + highlights, drawn over the refraction
  private streakSprite!: HTMLCanvasElement;
  private streaks: Streak[] = [];

  private readonly onResize = () => {
    clearTimeout(this.resizeTimer);
    this.resizeTimer = setTimeout(() => this.setup(), 200);
  };
  private readonly onVisibility = () => {
    if (!this.animated) return;
    if (document.hidden) {
      cancelAnimationFrame(this.rafId);
    } else {
      this.lastTime = 0;
      this.rafId = requestAnimationFrame(this.tick);
    }
  };

  constructor(private zone: NgZone) {}

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.dropSprite = this.buildDropSprite();
      this.streakSprite = this.buildStreakSprite();
      this.setup();
      window.addEventListener('resize', this.onResize, { passive: true });
      document.addEventListener('visibilitychange', this.onVisibility);
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.rafId);
    clearTimeout(this.resizeTimer);
    window.removeEventListener('resize', this.onResize);
    document.removeEventListener('visibilitychange', this.onVisibility);
  }

  private setup(): void {
    cancelAnimationFrame(this.rafId);
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    const stillOnly =
      window.matchMedia('(pointer: coarse)').matches ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      this.width < 768;
    // Full resolution only where it is cheap; drops are soft enough to hide it.
    this.dpr = Math.min(window.devicePixelRatio || 1, stillOnly ? 2 : 1.5);

    const scene = this.sizeCanvas(this.sceneRef.nativeElement);
    const glass = this.sizeCanvas(this.glassRef.nativeElement);
    this.glassCtx = glass.getContext('2d')!;
    this.mist = this.sizeCanvas(document.createElement('canvas'));
    this.mistCtx = this.mist.getContext('2d')!;

    const sharpScene = this.paintScene(scene);
    this.refractSource = this.flip(sharpScene);

    this.drops = [];
    this.streaks = Array.from({ length: Math.round(this.width * this.height * STREAK_DENSITY) }, () => this.newStreak(true));
    this.frame = 0;
    this.slowFrames = 0;
    this.maxDrops = Math.round(MAX_DROPS * Math.min(1, (this.width * this.height) / (1600 * 900)));

    if (stillOnly) {
      this.animated = false;
      for (let i = 0; i < STATIC_WARMUP_FRAMES; i++) this.step(1);
      this.render();
      return;
    }
    this.animated = true;
    for (let i = 0; i < 120; i++) this.step(1);
    this.lastTime = 0;
    this.rafId = requestAnimationFrame(this.tick);
  }

  private readonly tick = (time: number) => {
    const elapsed = this.lastTime ? time - this.lastTime : 16.7;
    this.lastTime = time;
    this.guardFramerate(elapsed);
    if (!this.animated) return;
    this.step(Math.min(elapsed / 16.7, 3));
    this.render();
    this.rafId = requestAnimationFrame(this.tick);
  };

  // Halve the drop budget after a run of slow frames, then freeze on the
  // current (still nice) frame if even that is too heavy.
  private guardFramerate(elapsed: number): void {
    if (this.frame < 60 || document.hidden) return;
    this.slowFrames = elapsed > SLOW_FRAME_MS ? this.slowFrames + 1 : Math.max(0, this.slowFrames - 1);
    if (this.slowFrames < 90) return;
    this.slowFrames = 0;
    if (this.maxDrops > 40) {
      this.maxDrops = Math.round(this.maxDrops / 2);
      this.drops.length = Math.min(this.drops.length, this.maxDrops);
    } else {
      this.animated = false;
    }
  }

  private sizeCanvas(canvas: HTMLCanvasElement): HTMLCanvasElement {
    canvas.width = Math.round(this.width * this.dpr);
    canvas.height = Math.round(this.height * this.dpr);
    const ctx = canvas.getContext('2d')!;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    return canvas;
  }

  // The night behind the glass: the site background with two soft glows.
  // Returns a less blurred, brighter copy, which is what the drops refract
  // (a lens sees the scene sharper than the eye focused on the pane does).
  private paintScene(target: HTMLCanvasElement): HTMLCanvasElement {
    const css = getComputedStyle(document.documentElement);
    const bg = css.getPropertyValue('--color-bg').trim() || '#0f1419';
    const lights = this.sizeCanvas(document.createElement('canvas'));
    const ctx = lights.getContext('2d')!;
    const w = this.width;
    const h = this.height;
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);
    this.glow(ctx, w * 0.2, h * 0.8, Math.max(w, h) * 0.5, `rgba(120, 119, 198, 0.3)`);
    this.glow(ctx, w * 0.8, h * 0.2, Math.max(w, h) * 0.5, `rgba(255, 119, 198, 0.15)`);

    const out = target.getContext('2d')!;
    out.save();
    out.setTransform(1, 0, 0, 1, 0, 0);
    out.filter = `blur(${Math.round(10 * this.dpr)}px)`;
    out.drawImage(lights, 0, 0);
    out.restore();

    const sharp = this.sizeCanvas(document.createElement('canvas'));
    const sctx = sharp.getContext('2d')!;
    sctx.setTransform(1, 0, 0, 1, 0, 0);
    // A drop concentrates light: its image of the scene is brighter and richer.
    sctx.filter = `blur(${Math.round(2 * this.dpr)}px) brightness(2.1) saturate(1.35)`;
    sctx.drawImage(lights, 0, 0);
    return sharp;
  }

  private glow(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string): void {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color);
    g.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, this.width, this.height);
  }

  private flip(source: HTMLCanvasElement): HTMLCanvasElement {
    const out = document.createElement('canvas');
    out.width = source.width;
    out.height = source.height;
    const ctx = out.getContext('2d')!;
    ctx.translate(out.width, out.height);
    ctx.scale(-1, -1);
    ctx.drawImage(source, 0, 0);
    return out;
  }

  // Shading of a water drop, drawn over its refraction: dark rim where light
  // bends away, a bright caustic crescent at the bottom, a specular glint top-left.
  private buildDropSprite(): HTMLCanvasElement {
    const size = 128;
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d')!;
    const m = size / 2;

    const rim = ctx.createRadialGradient(m, m * 0.92, m * 0.45, m, m, m);
    rim.addColorStop(0, 'rgba(0, 0, 0, 0)');
    rim.addColorStop(0.75, 'rgba(0, 0, 0, 0.12)');
    rim.addColorStop(0.93, 'rgba(0, 0, 0, 0.3)');
    rim.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = rim;
    ctx.fillRect(0, 0, size, size);

    const caustic = ctx.createRadialGradient(m, m * 1.55, m * 0.1, m, m * 1.3, m * 0.75);
    caustic.addColorStop(0, 'rgba(255, 255, 255, 0.35)');
    caustic.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = caustic;
    ctx.beginPath();
    ctx.arc(m, m, m * 0.96, 0, Math.PI * 2);
    ctx.fill();

    const glint = ctx.createRadialGradient(m * 0.68, m * 0.6, 0, m * 0.68, m * 0.6, m * 0.3);
    glint.addColorStop(0, 'rgba(255, 255, 255, 0.85)');
    glint.addColorStop(0.35, 'rgba(255, 255, 255, 0.3)');
    glint.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = glint;
    ctx.fillRect(0, 0, size, size);
    return c;
  }

  // A streak of distant rain. Three depths: far ones are thin, faint and slow.
  private newStreak(anywhere: boolean): Streak {
    const depth = Math.random();
    const length = 18 + depth * 46;
    return {
      // The wind shifts streaks right as they fall, so start some off-screen left.
      x: -this.height * WIND + Math.random() * (this.width + this.height * WIND),
      y: anywhere ? Math.random() * this.height : -length - Math.random() * this.height * 0.3,
      length,
      speed: 9 + depth * 16 + Math.random() * 3,
      alpha: 0.035 + depth * 0.075,
      width: 0.6 + depth * 0.9,
    };
  }

  private buildStreakSprite(): HTMLCanvasElement {
    const c = document.createElement('canvas');
    c.width = 4;
    c.height = 64;
    const ctx = c.getContext('2d')!;
    const g = ctx.createLinearGradient(0, 0, 0, 64);
    g.addColorStop(0, 'rgba(210, 225, 255, 0)');
    g.addColorStop(0.7, 'rgba(210, 225, 255, 0.9)');
    g.addColorStop(1, 'rgba(210, 225, 255, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 4, 64);
    return c;
  }

  private newDrop(x: number, y: number, r: number): Drop {
    return {
      x, y, r,
      momentum: 0,
      momentumX: 0,
      spreadX: 0,
      spreadY: 0,
      lastTrailY: y,
      nextTrailGap: 8 + Math.random() * 30,
      shrink: 0,
      killed: false,
      // Mostly sticky drops with short runs; about one in eight finds a wet,
      // slippery path and races down.
      friction: Math.random() < 0.12 ? 0.975 + Math.random() * 0.015 : 0.88 + Math.random() * 0.08,
      grip: 0.3 + Math.random() * 1.6,
    };
  }

  private step(k: number): void {
    this.frame++;
    const w = this.width;
    const h = this.height;

    // Rain keeps hitting the pane: mostly small drops, sometimes a fat one.
    let spawn = SPAWN_PER_FRAME * k;
    while (spawn > 0 && this.drops.length < this.maxDrops) {
      if (Math.random() < spawn) {
        const r = MIN_R + Math.pow(Math.random(), 3) * (MAX_R - MIN_R);
        this.drops.push(this.newDrop(Math.random() * w, Math.random() * h * 0.95, r));
      }
      spawn -= 1;
    }

    for (let i = 0; i < this.streaks.length; i++) {
      const st = this.streaks[i];
      st.y += st.speed * k;
      if (st.y > this.height + st.length) this.streaks[i] = this.newStreak(false);
    }

    this.addMist(k);

    const fresh: Drop[] = [];
    for (const d of this.drops) {
      if (d.killed) continue;

      // Clinging drops occasionally give way; heavier drops give way more often
      // and in stronger bursts. Friction then catches them again: that stop-and-go
      // is what makes real drops look irregular.
      if (d.r > SLIDE_R && Math.random() < ((d.r - SLIDE_R) / (MAX_R - SLIDE_R)) * 0.06 * d.grip * k) {
        d.momentum += Math.random() * (d.r / MAX_R) * 4 * (Math.random() < 0.2 ? 2.5 : 1);
      }
      if (d.r > SLIDE_R && d.momentum > 0) {
        d.momentumX += (Math.random() - 0.5) * 0.35 * k;
      }
      d.momentum *= Math.pow(d.friction, k);
      d.momentumX *= Math.pow(0.9, k);
      d.y += d.momentum * k;
      d.x += d.momentumX * k;

      // A moving drop leaves small droplets behind and loses a little water.
      if (d.momentum > 0.6 && d.y - d.lastTrailY > d.nextTrailGap) {
        d.lastTrailY = d.y;
        d.nextTrailGap = 8 + Math.random() * Math.random() * (60 + d.r * 3);
        const t = this.newDrop(
          d.x + (Math.random() - 0.5) * d.r * 0.8,
          d.y - d.r * (0.6 + Math.random() * 0.8),
          d.r * (0.1 + Math.pow(Math.random(), 2) * 0.32),
        );
        t.spreadY = d.momentum * 0.05;
        t.shrink = 0.002 + Math.random() * 0.006; // trail droplets slowly evaporate
        fresh.push(t);
        d.r *= 0.985;
      }

      // Shape: stretched while sliding, round when still.
      d.spreadY += (Math.min(d.momentum * 0.09, 0.35) - d.spreadY) * 0.2 * k;
      d.spreadX += (Math.min(Math.abs(d.momentumX) * 0.3, 0.2) - d.spreadX) * 0.2 * k;

      d.r -= d.shrink * k;
      if (d.r < MIN_R * 0.35 || d.y - d.r > h + 20) d.killed = true;
    }

    // Merging: a drop runs into another and swallows it.
    const list = this.drops;
    for (let i = 0; i < list.length; i++) {
      const a = list[i];
      if (a.killed || a.momentum < 0.2) continue;
      for (let j = 0; j < list.length; j++) {
        const b = list[j];
        if (i === j || b.killed) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const reach = (a.r + b.r) * 0.8;
        if (dx * dx + dy * dy < reach * reach) {
          const [big, small] = a.r >= b.r ? [a, b] : [b, a];
          big.r = Math.min(Math.sqrt(big.r * big.r + small.r * small.r * 0.8), MAX_R * 1.25);
          big.momentum = Math.max(big.momentum, small.momentum) + 0.4;
          big.x = (big.x * big.r + small.x * small.r) / (big.r + small.r);
          small.killed = true;
        }
      }
      // Wipe the mist under a sliding drop.
      if (a.momentum > 0.5) {
        this.mistCtx.globalCompositeOperation = 'destination-out';
        this.mistCtx.beginPath();
        this.mistCtx.arc(a.x, a.y, a.r * 1.1, 0, Math.PI * 2);
        this.mistCtx.fill();
        this.mistCtx.globalCompositeOperation = 'source-over';
      }
    }

    this.drops = list.filter(d => !d.killed).concat(fresh).slice(-this.maxDrops);
  }

  // Fine mist of tiny droplets that keeps settling on the glass and slowly
  // evaporates, so trails stay visible for a while and then fill back in.
  private addMist(k: number): void {
    const ctx = this.mistCtx;
    const n = Math.round(MIST_PER_FRAME * k);
    for (let i = 0; i < n; i++) {
      const r = 0.6 + Math.random() * 1.8;
      const x = Math.random() * this.width;
      const y = Math.random() * this.height;
      ctx.globalAlpha = 0.35 + Math.random() * 0.4;
      ctx.drawImage(this.dropSprite, x - r, y - r, r * 2, r * 2);
      ctx.fillStyle = 'rgba(210, 225, 255, 0.18)';
      ctx.beginPath();
      ctx.arc(x - r * 0.25, y - r * 0.25, r * 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (this.frame % MIST_FADE_EVERY === 0) {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
      ctx.fillRect(0, 0, this.width, this.height);
      ctx.globalCompositeOperation = 'source-over';
    }
  }

  private render(): void {
    const ctx = this.glassCtx;
    const w = this.width;
    const h = this.height;
    const dpr = this.dpr;
    ctx.clearRect(0, 0, w, h);

    // Distant rain, slanted by the wind with a single shear for all streaks.
    ctx.save();
    ctx.transform(1, 0, WIND, 1, 0, 0);
    for (const st of this.streaks) {
      ctx.globalAlpha = st.alpha;
      ctx.drawImage(this.streakSprite, st.x, st.y - st.length, st.width, st.length);
    }
    ctx.restore();
    ctx.globalAlpha = 1;

    ctx.drawImage(this.mist, 0, 0, w, h);

    for (const d of this.drops) {
      const rx = d.r * (1 - d.spreadX * 0.5);
      const ry = d.r * (1 + d.spreadY);
      // The drop sits slightly below its center of mass while sliding (tail on top).
      const cy = d.y + ry * d.spreadY * 0.6;

      // Refraction: a water lens shows a wide, inverted view of what is behind it.
      const s = d.r * REFRACTION;
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(d.x, cy, rx, ry, 0, 0, Math.PI * 2);
      ctx.clip();
      ctx.drawImage(
        this.refractSource,
        (w - d.x - s) * dpr, (h - cy - s) * dpr, s * 2 * dpr, s * 2 * dpr,
        d.x - rx, cy - ry, rx * 2, ry * 2,
      );
      ctx.restore();
      ctx.drawImage(this.dropSprite, d.x - rx, cy - ry, rx * 2, ry * 2);
    }
  }
}
