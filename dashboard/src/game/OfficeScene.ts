import * as Phaser from "phaser";

// ────────────────────────────────────────────────────────────
// Office scene — 1408×768 canvas matching office-bg.png
//
// Depth occlusion: The background is rendered as horizontal
// strips at different depths. Characters depth-sort by Y,
// so they naturally appear behind foreground furniture and
// in front of background furniture.
// ────────────────────────────────────────────────────────────

const GW = 1408;
const GH = 768;

// ── Depth strips ──
// The background is split into horizontal bands. Each band
// renders at depth = its bottom Y edge. Characters with Y
// between two strip boundaries sort between those strips.
//
// Breakpoints chosen at furniture bottom-edges (from bbox data):
//   246 (desk_bc), 369 (desk_lu), 477 (desk_ll/lamp),
//   538 (couch/plants_front), 676 (table/bookshelves)

const DEPTH_STRIPS = [
  { y: 0,   h: 246, depth: 246 },   // back wall, whiteboard, desk_bc
  { y: 246, h: 123, depth: 369 },   // desk_lu, desk_ru, cooler top
  { y: 369, h: 108, depth: 477 },   // desk_ll, desk_rl, lamp
  { y: 477, h: 61,  depth: 538 },   // couch, front plants
  { y: 538, h: 138, depth: 676 },   // table, bookshelves
  { y: 676, h: 92,  depth: 768 },   // bottom edge
];

// ── Navigation graph ──

interface NavNode {
  x: number;
  y: number;
  neighbors: string[];
  interact?: {
    label: string;
    sitting?: boolean;
    flipX?: boolean;
    effect?: { dx: number; dy: number; type: string };
  };
}

function p(xPct: number, yPct: number) {
  return { x: Math.round((xPct / 100) * GW), y: Math.round((yPct / 100) * GH) };
}

// Character positions calibrated to chair/standing spots.
// Y values chosen so characters depth-sort correctly relative to strips.
const NAV: Record<string, NavNode> = {
  // Floor junctions (open walkable corridors)
  center: { ...p(46, 60), neighbors: ["north", "south", "west", "east"] },
  north:  { ...p(42, 50), neighbors: ["center", "nw", "ne", "whiteboard", "desk_bc"] },
  south:  { ...p(46, 74), neighbors: ["center", "sw", "se", "table_l", "table_r", "bookshelf"] },
  west:   { ...p(24, 56), neighbors: ["center", "nw", "sw", "plants"] },
  east:   { ...p(70, 54), neighbors: ["center", "ne", "se", "cooler"] },
  nw:     { ...p(26, 50), neighbors: ["north", "west", "desk_lu", "desk_ll"] },
  ne:     { ...p(62, 48), neighbors: ["north", "east", "desk_ru"] },
  sw:     { ...p(24, 66), neighbors: ["south", "west"] },
  se:     { ...p(72, 66), neighbors: ["south", "east", "desk_rl", "couch"] },

  // Desks — Y placed just below desk bottom edge so character is in front
  desk_lu: {
    ...p(16, 50),
    neighbors: ["nw"],
    interact: { label: "Working", sitting: true, effect: { dx: -8, dy: -80, type: "screen" } },
  },
  desk_ll: {
    ...p(28, 64),
    neighbors: ["nw"],
    interact: { label: "Working", sitting: true, effect: { dx: 0, dy: -75, type: "screen" } },
  },
  desk_bc: {
    ...p(46, 34),
    neighbors: ["north"],
    interact: { label: "Working", sitting: true, effect: { dx: 0, dy: -75, type: "screen" } },
  },
  desk_ru: {
    ...p(66, 44),
    neighbors: ["ne"],
    interact: { label: "Working", sitting: true, flipX: true, effect: { dx: 8, dy: -75, type: "screen" } },
  },
  desk_rl: {
    ...p(82, 60),
    neighbors: ["se"],
    interact: { label: "Working", sitting: true, flipX: true, effect: { dx: 8, dy: -75, type: "screen" } },
  },

  // Interactive objects
  cooler: {
    ...p(88, 52),
    neighbors: ["east"],
    interact: { label: "Getting water", flipX: true, effect: { dx: -16, dy: -25, type: "water" } },
  },
  couch: {
    ...p(74, 68),
    neighbors: ["se"],
    interact: { label: "Resting", sitting: true, flipX: true, effect: { dx: 16, dy: -65, type: "zzz" } },
  },
  table_l: {
    ...p(40, 85),
    neighbors: ["south"],
    interact: { label: "Chatting", sitting: true, effect: { dx: 22, dy: -60, type: "chat" } },
  },
  table_r: {
    ...p(52, 86),
    neighbors: ["south"],
    interact: { label: "Chatting", sitting: true, flipX: true, effect: { dx: -22, dy: -60, type: "chat" } },
  },
  whiteboard: {
    ...p(40, 28),
    neighbors: ["north"],
    interact: { label: "Planning", effect: { dx: 0, dy: -50, type: "think" } },
  },
  bookshelf: {
    ...p(70, 88),
    neighbors: ["south"],
    interact: { label: "Reading", flipX: true, effect: { dx: -20, dy: -50, type: "book" } },
  },
  plants: {
    ...p(10, 66),
    neighbors: ["west"],
    interact: { label: "Watering plants", effect: { dx: 16, dy: -35, type: "sparkle" } },
  },
};

const HOME_DESKS = ["desk_lu", "desk_ll", "desk_bc", "desk_ru", "desk_rl"];
const ALL_INTERACT = Object.keys(NAV).filter((k) => NAV[k].interact);

// ── BFS pathfinding ──

function findPath(from: string, to: string): string[] {
  if (from === to) return [from];
  const queue: string[][] = [[from]];
  const visited = new Set([from]);
  while (queue.length) {
    const path = queue.shift()!;
    const cur = path[path.length - 1];
    for (const nb of NAV[cur]?.neighbors || []) {
      if (nb === to) return [...path, nb];
      if (!visited.has(nb)) {
        visited.add(nb);
        queue.push([...path, nb]);
      }
    }
  }
  return [from];
}

// ── Color values ──

const COLOR_HEX: Record<string, string> = {
  indigo: "#818cf8",
  pink: "#f472b6",
  emerald: "#6ee7b3",
  amber: "#fcd34d",
  sky: "#7dd3fc",
};

// ── Public types ──

export interface EmployeeData {
  id: string;
  name: string;
  avatar: string;
  color: string;
  status: "busy" | "idle";
}

export interface OfficeSceneData {
  employees: EmployeeData[];
  onClick: (id: string) => void;
}

// ── Character object ──

interface CharObj {
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Image;
  label: Phaser.GameObjects.Text;
  dot: Phaser.GameObjects.Arc | null;
  curNode: string;
  homeDesk: string;
  isBusy: boolean;
  isWalking: boolean;
  walkBob: Phaser.Tweens.Tween | null;
  idleTween: Phaser.Tweens.Tween | null;
  effectObjs: Phaser.GameObjects.GameObject[];
}

// ── Scene ──

export default class OfficeScene extends Phaser.Scene {
  private chars = new Map<string, CharObj>();
  private occupied = new Set<string>();
  private emps: EmployeeData[] = [];
  private clickCb: (id: string) => void = () => {};

  constructor() {
    super({ key: "office" });
  }

  init(data: OfficeSceneData) {
    this.emps = data?.employees ?? [];
    this.clickCb = data?.onClick ?? (() => {});
  }

  preload() {
    this.load.image("bg", "/office/office-bg.png");
    for (const e of this.emps) {
      this.load.image(e.id, e.avatar);
    }
  }

  create() {
    // Render background as depth-sorted horizontal strips.
    // Each strip is a copy of the full background, cropped to its band,
    // positioned so the visible pixels stay at correct screen coordinates.
    for (const strip of DEPTH_STRIPS) {
      const img = this.add.image(0, 0, "bg").setOrigin(0, 0).setDepth(strip.depth);
      img.setCrop(0, strip.y, GW, strip.h);
    }

    // Create characters
    this.emps.forEach((emp, i) => {
      const desk = HOME_DESKS[i] || HOME_DESKS[0];
      const node = NAV[desk];

      const container = this.add.container(node.x, node.y);

      // Sprite — bottom-center anchored
      const sprite = this.add.image(0, 0, emp.id).setOrigin(0.5, 1);
      const targetH = 120;
      sprite.setScale(targetH / sprite.height);
      if (node.interact?.flipX) sprite.setFlipX(true);

      // Name label below feet
      const label = this.add
        .text(0, 6, emp.name.split(" ")[0], {
          fontSize: "12px",
          fontFamily: "system-ui, -apple-system, sans-serif",
          color: COLOR_HEX[emp.color] || "#ffffff",
          stroke: "#000000",
          strokeThickness: 3,
          align: "center",
        })
        .setOrigin(0.5, 0);

      container.add([sprite, label]);

      // Status dot (green pulse for busy)
      let dot: Phaser.GameObjects.Arc | null = null;
      if (emp.status === "busy") {
        const sw = (sprite.width * sprite.scaleX) / 2;
        const sh = sprite.height * sprite.scaleY;
        dot = this.add.circle(sw - 2, -sh + 8, 5, 0x34d399);
        container.add(dot);
        this.tweens.add({
          targets: dot,
          alpha: { from: 1, to: 0.3 },
          duration: 800,
          yoyo: true,
          repeat: -1,
        });
      }

      // Click + hover
      sprite.setInteractive({ cursor: "pointer", pixelPerfect: false });
      sprite.on("pointerdown", () => this.clickCb(emp.id));
      sprite.on("pointerover", () => {
        this.tweens.add({ targets: container, scaleX: 1.1, scaleY: 1.1, duration: 120, ease: "Back.easeOut" });
      });
      sprite.on("pointerout", () => {
        this.tweens.add({ targets: container, scaleX: 1, scaleY: 1, duration: 120 });
      });

      container.setDepth(Math.round(node.y));

      const char: CharObj = {
        container,
        sprite,
        label,
        dot,
        curNode: desk,
        homeDesk: desk,
        isBusy: emp.status === "busy",
        isWalking: false,
        walkBob: null,
        idleTween: null,
        effectObjs: [],
      };

      this.chars.set(emp.id, char);
      this.occupied.add(desk);

      this.applySitOffset(char);
      this.startTypingAnim(char);
      this.showEffect(emp.id);

      const delay = 3000 + i * 2000 + Math.random() * 5000;
      this.time.delayedCall(delay, () => this.pickNext(emp.id));
    });
  }

  update() {
    for (const [, c] of this.chars) {
      c.container.setDepth(Math.round(c.container.y));
    }
  }

  // ── Sitting offset ──

  private applySitOffset(char: CharObj) {
    char.sprite.y = 10;
  }

  private clearSitOffset(char: CharObj) {
    char.sprite.y = 0;
  }

  // ── Animations ──

  private startTypingAnim(char: CharObj) {
    char.idleTween?.destroy();
    char.idleTween = this.tweens.add({
      targets: char.sprite,
      y: char.sprite.y - 2,
      angle: { from: -0.5, to: 0.5 },
      duration: 500,
      yoyo: true,
      repeat: -1,
      ease: "Sine.easeInOut",
    });
  }

  private startIdleAnim(char: CharObj) {
    char.idleTween?.destroy();
    char.idleTween = this.tweens.add({
      targets: char.sprite,
      y: -3,
      duration: 1800,
      yoyo: true,
      repeat: -1,
      ease: "Sine.easeInOut",
    });
  }

  private startWalkBob(char: CharObj) {
    char.walkBob?.destroy();
    char.walkBob = this.tweens.add({
      targets: char.sprite,
      y: -7,
      angle: { from: -2.5, to: 2.5 },
      duration: 350,
      yoyo: true,
      repeat: -1,
      ease: "Sine.easeInOut",
    });
  }

  private stopWalkBob(char: CharObj) {
    char.walkBob?.destroy();
    char.walkBob = null;
    char.sprite.y = 0;
    char.sprite.angle = 0;
  }

  // ── Effects ──

  private showEffect(empId: string) {
    const char = this.chars.get(empId);
    if (!char) return;
    this.clearEffects(char);

    const node = NAV[char.curNode];
    const eff = node?.interact?.effect;
    if (!eff) return;

    const ex = char.container.x + eff.dx;
    const ey = char.container.y + eff.dy;
    const depth = char.container.depth + 1;

    if (eff.type === "screen") {
      const rect = this.add.rectangle(ex, ey, 24, 16, 0x64c8ff, 0.5).setDepth(depth);
      this.tweens.add({
        targets: rect,
        alpha: { from: 0.3, to: 0.7 },
        duration: 1000,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
      char.effectObjs.push(rect);
      return;
    }

    const emoji: Record<string, string> = {
      water: "\u{1F4A7}",
      zzz: "\u{1F4A4}",
      chat: "\u{1F4AC}",
      think: "\u{1F4A1}",
      book: "\u{1F4D6}",
      sparkle: "\u{2728}",
    };

    const ch = emoji[eff.type];
    if (!ch) return;

    const txt = this.add.text(ex, ey, ch, { fontSize: "18px" }).setOrigin(0.5).setDepth(depth);
    char.effectObjs.push(txt);

    if (eff.type === "zzz") {
      this.tweens.add({
        targets: txt,
        y: ey - 20,
        alpha: { from: 0.9, to: 0 },
        scale: { from: 0.7, to: 1.4 },
        duration: 2800,
        repeat: -1,
        ease: "Sine.easeOut",
      });
    } else if (eff.type === "water") {
      this.tweens.add({
        targets: txt,
        y: ey + 14,
        alpha: { from: 1, to: 0 },
        duration: 1400,
        repeat: -1,
        ease: "Quad.easeIn",
      });
    } else {
      this.tweens.add({
        targets: txt,
        y: ey - 6,
        scale: { from: 0.85, to: 1.15 },
        alpha: { from: 0.7, to: 1 },
        duration: 1600,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
  }

  private clearEffects(char: CharObj) {
    for (const obj of char.effectObjs) obj.destroy();
    char.effectObjs = [];
  }

  // ── Behavior ──

  private pickNext(empId: string) {
    const char = this.chars.get(empId);
    if (!char || char.isWalking) return;

    const cur = char.curNode;
    const atDesk = HOME_DESKS.includes(cur);
    let dest = cur;

    if (char.isBusy) {
      if (atDesk && Math.random() < 0.75) {
        dest = cur;
      } else if (!atDesk) {
        dest = char.homeDesk;
      } else {
        const breaks = ["cooler", "couch", "table_l", "table_r"].filter((s) => !this.occupied.has(s));
        dest = breaks.length ? breaks[Math.floor(Math.random() * breaks.length)] : cur;
      }
    } else {
      const roll = Math.random();
      if (roll < 0.15) {
        dest = cur;
      } else if (roll < 0.3 && !atDesk) {
        dest = char.homeDesk;
      } else {
        const avail = ALL_INTERACT.filter((s) => !this.occupied.has(s) && s !== cur);
        dest = avail.length ? avail[Math.floor(Math.random() * avail.length)] : cur;
      }
    }

    if (dest === cur) {
      const delay = 4000 + Math.random() * 8000;
      this.time.delayedCall(delay, () => this.pickNext(empId));
    } else {
      this.walkTo(empId, dest);
    }
  }

  private walkTo(empId: string, dest: string) {
    const char = this.chars.get(empId);
    if (!char) return;

    const path = findPath(char.curNode, dest);
    if (path.length <= 1) {
      this.time.delayedCall(3000, () => this.pickNext(empId));
      return;
    }

    char.isWalking = true;
    this.occupied.delete(char.curNode);
    this.clearEffects(char);
    char.idleTween?.destroy();
    this.clearSitOffset(char);
    this.startWalkBob(char);

    const walkSeg = (idx: number) => {
      if (idx >= path.length - 1) {
        this.stopWalkBob(char);
        char.isWalking = false;
        char.curNode = dest;
        this.occupied.add(dest);

        const interact = NAV[dest]?.interact;
        char.sprite.setFlipX(!!interact?.flipX);

        if (interact?.sitting) {
          this.applySitOffset(char);
          this.startTypingAnim(char);
        } else {
          this.startIdleAnim(char);
        }

        this.showEffect(empId);

        const delay = 6000 + Math.random() * 12000;
        this.time.delayedCall(delay, () => this.pickNext(empId));
        return;
      }

      const fromNode = NAV[path[idx]];
      const toNode = NAV[path[idx + 1]];
      const dist = Phaser.Math.Distance.Between(fromNode.x, fromNode.y, toNode.x, toNode.y);
      const duration = Math.max((dist / 55) * 1000, 600);

      char.sprite.setFlipX(toNode.x < fromNode.x);

      this.tweens.add({
        targets: char.container,
        x: toNode.x,
        y: toNode.y,
        duration,
        ease: "Sine.easeInOut",
        onComplete: () => walkSeg(idx + 1),
      });
    };

    walkSeg(0);
  }
}
