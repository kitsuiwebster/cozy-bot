import { CozySound } from '../../services/cozybot.service';

export interface CssPieSegment {
  name: string;
  color: string;
  valueLabel: string;
  percentLabel: string;
}

export interface CssPie {
  gradient: string;
  segments: CssPieSegment[];
  totalLabel: string;
}

// Validated dark-mode categorical palette (fixed slot order, never cycled).
// Gray is reserved for the "Other" fold and deliberately reads as neutral.
const PIE_SERIES_COLORS = ['#3987e5', '#008300', '#d55181', '#c98500', '#199e70', '#d95926', '#9085e9', '#e66767'];
const PIE_OTHER_COLOR = '#8a8a86';
const PIE_TOP_SLICES = 7;

// Color follows the category entity, never its rank.
const PIE_CATEGORIES: { [emoji: string]: { label: string; color: string } } = {
  '🌧️': { label: '🌧️ Rain', color: '#3987e5' },
  '🌊': { label: '🌊 Sea', color: '#199e70' },
  '✨': { label: '✨ Sparkles', color: '#c98500' },
  '🎶': { label: '🎶 Music', color: '#9085e9' },
  '🎵': { label: '🎶 Music', color: '#9085e9' },
  '📡': { label: '📡 Noise', color: '#d55181' },
};

function formatValue(seconds: number): string {
  const s = Math.floor(seconds);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  return parts.length > 0 ? parts.join(' ') : '0m';
}

function formatPercent(value: number, total: number): string {
  if (!total || total <= 0) return '0%';
  return `${((value / total) * 100).toFixed(1)}%`;
}

function firstEmoji(text: string): string {
  const re = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}️)(?:‍(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}️))*/u;
  const m = re.exec(text);
  return m ? m[0] : '';
}

// Builds a pure-CSS donut: a conic-gradient with a surface gap between
// slices, plus precomputed legend rows.
function buildCssPie(items: { name: string; value: number; color: string }[]): CssPie | null {
  const visible = items.filter(item => item.value > 0);
  const total = visible.reduce((sum, item) => sum + item.value, 0);
  if (visible.length === 0 || total <= 0) return null;

  // ~2px gap at this donut radius; a single full slice needs none.
  const gapDeg = visible.length > 1 ? 1.4 : 0;
  const stops: string[] = [];
  let angle = 0;

  visible.forEach(item => {
    const sweep = (item.value / total) * 360;
    const start = Math.min(angle + gapDeg / 2, angle + sweep);
    const end = Math.max(start, angle + sweep - gapDeg / 2);
    stops.push(`transparent ${angle.toFixed(3)}deg ${start.toFixed(3)}deg`);
    stops.push(`${item.color} ${start.toFixed(3)}deg ${end.toFixed(3)}deg`);
    stops.push(`transparent ${end.toFixed(3)}deg ${(angle + sweep).toFixed(3)}deg`);
    angle += sweep;
  });

  return {
    gradient: `conic-gradient(${stops.join(', ')})`,
    segments: visible.map(item => ({
      name: item.name,
      color: item.color,
      valueLabel: formatValue(item.value),
      percentLabel: formatPercent(item.value, total),
    })),
    totalLabel: formatValue(total),
  };
}

// Per-sound donut: top slices in fixed palette order, the rest folded into
// a neutral "Other" slice.
export function buildSoundsPie(sounds: CozySound[]): CssPie | null {
  const sorted = [...sounds].filter(s => s.total_time > 0).sort((a, b) => b.total_time - a.total_time);
  const top = sorted.slice(0, PIE_TOP_SLICES);
  const rest = sorted.slice(PIE_TOP_SLICES);

  const items = top.map((sound, index) => ({
    name: sound.display_name,
    value: sound.total_time,
    color: PIE_SERIES_COLORS[index],
  }));

  if (rest.length > 0) {
    items.push({
      name: `Other (${rest.length} sounds)`,
      value: rest.reduce((sum, s) => sum + s.total_time, 0),
      color: PIE_OTHER_COLOR,
    });
  }

  return buildCssPie(items);
}

// Category donut: sounds grouped by their first emoji, merged into fixed
// categories (🎶 and 🎵 are both Music) with fixed per-category colors.
export function buildCategoryPie(sounds: CozySound[]): CssPie | null {
  const byCategory: { [label: string]: { value: number; color: string } } = {};
  sounds.forEach(sound => {
    const emoji = firstEmoji(sound.display_name);
    if (!emoji) return;
    const category = PIE_CATEGORIES[emoji] || { label: emoji, color: PIE_OTHER_COLOR };
    if (!byCategory[category.label]) byCategory[category.label] = { value: 0, color: category.color };
    byCategory[category.label].value += sound.total_time;
  });

  const items = Object.entries(byCategory)
    .map(([label, entry]) => ({ name: label, value: entry.value, color: entry.color }))
    .sort((a, b) => b.value - a.value);

  return buildCssPie(items);
}
