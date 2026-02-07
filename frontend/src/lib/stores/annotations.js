import { writable, derived } from 'svelte/store';

// Annotation colors (chess.com style)
export const ANNOTATION_COLORS = {
  green: { fill: 'rgba(21, 120, 27, 0.8)', stroke: '#15781B' },
  red: { fill: 'rgba(136, 0, 27, 0.8)', stroke: '#88001B' },
  blue: { fill: 'rgba(0, 100, 180, 0.8)', stroke: '#0064B4' },
  yellow: { fill: 'rgba(204, 170, 0, 0.8)', stroke: '#CCAA00' },
  orange: { fill: 'rgba(240, 127, 9, 0.8)', stroke: '#F07F09' },
};

// Current annotation tool
export const annotationTool = writable('arrow'); // 'arrow', 'highlight', 'none'

// Current annotation color
export const annotationColor = writable('green');

// Arrows: array of { from, to, color }
export const arrows = writable([]);

// Highlighted squares: array of { square, color }
export const highlights = writable([]);

// Whether annotations are enabled
export const annotationsEnabled = writable(true);

// Add an arrow
export function addArrow(from, to, color = null) {
  arrows.update(arr => {
    // Remove existing arrow with same from/to
    const filtered = arr.filter(a => !(a.from === from && a.to === to));
    // Add new arrow
    return [...filtered, { from, to, color: color || 'green' }];
  });
}

// Remove an arrow
export function removeArrow(from, to) {
  arrows.update(arr => arr.filter(a => !(a.from === from && a.to === to)));
}

// Toggle arrow (add if not exists, remove if exists with same color, change color otherwise)
export function toggleArrow(from, to, color) {
  arrows.update(arr => {
    const existing = arr.find(a => a.from === from && a.to === to);
    if (existing) {
      if (existing.color === color) {
        // Same color - remove it
        return arr.filter(a => !(a.from === from && a.to === to));
      } else {
        // Different color - update it
        return arr.map(a =>
          (a.from === from && a.to === to) ? { ...a, color } : a
        );
      }
    } else {
      // Add new arrow
      return [...arr, { from, to, color }];
    }
  });
}

// Add a highlight
export function addHighlight(square, color = null) {
  highlights.update(arr => {
    const filtered = arr.filter(h => h.square !== square);
    return [...filtered, { square, color: color || 'green' }];
  });
}

// Remove a highlight
export function removeHighlight(square) {
  highlights.update(arr => arr.filter(h => h.square !== square));
}

// Toggle highlight
export function toggleHighlight(square, color) {
  highlights.update(arr => {
    const existing = arr.find(h => h.square === square);
    if (existing) {
      if (existing.color === color) {
        return arr.filter(h => h.square !== square);
      } else {
        return arr.map(h => h.square === square ? { ...h, color } : h);
      }
    } else {
      return [...arr, { square, color }];
    }
  });
}

// Clear all annotations
export function clearAnnotations() {
  arrows.set([]);
  highlights.set([]);
}

// Clear arrows only
export function clearArrows() {
  arrows.set([]);
}

// Clear highlights only
export function clearHighlights() {
  highlights.set([]);
}
