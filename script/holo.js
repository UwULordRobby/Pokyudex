/**
 * Pokyudex - Holo Engine (holo.js)
 * Handles dynamic vector texture generation and 3D pointer tracking.
 */

/* ==========================================================================
   1. PROCEDURAL VECTOR TEXTURE GENERATOR (SVG SPARKLES)
   ========================================================================== */

// Seeded random number generator for consistent particle placement
function mulberry32(seed) {
  return function() {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Mathematical SVG path generator for the classic 4-point star
function starPath(cx, cy, r) {
  const k = r * 0.32;
  return `M${cx.toFixed(1)} ${(cy-r).toFixed(1)} ` +
         `Q${(cx+k).toFixed(1)} ${(cy-k).toFixed(1)} ${(cx+r).toFixed(1)} ${cy.toFixed(1)} ` +
         `Q${(cx+k).toFixed(1)} ${(cy+k).toFixed(1)} ${cx.toFixed(1)} ${(cy+r).toFixed(1)} ` +
         `Q${(cx-k).toFixed(1)} ${(cy+k).toFixed(1)} ${(cx-r).toFixed(1)} ${cy.toFixed(1)} ` +
         `Q${(cx-k).toFixed(1)} ${(cy-k).toFixed(1)} ${cx.toFixed(1)} ${(cy-r).toFixed(1)} Z`;
}

// Assembles the inline SVG data URI based on parameter payload
function buildSparkleSvg({ seed=1, w=200, h=200, count=40, sizeMin=2, sizeMax=6, palette=['#ffffff'], starRatio=0.4 }) {
  const rnd = mulberry32(seed);
  let shapes = '';
  
  for (let i = 0; i < count; i++) {
    const x = rnd() * w;
    const y = rnd() * h;
    const size = sizeMin + rnd() * (sizeMax - sizeMin);
    const color = palette[Math.floor(rnd() * palette.length)];
    const op = (0.45 + rnd() * 0.5).toFixed(2);
    
    if (rnd() < starRatio) {
      shapes += `<path d="${starPath(x, y, size)}" fill="${color}" opacity="${op}"/>`;
    } else {
      shapes += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(size*0.32).toFixed(2)}" fill="${color}" opacity="${op}"/>`;
    }
  }
  
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${shapes}</svg>`;
  return 'url("data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg))) + '")';
}

/* ==========================================================================
   2. TEXTURE INITIALIZATION & CSS VAR INJECTION
   ========================================================================== */

function initializeHoloTextures() {
  const PALETTE_FULL = ['#5ef2c9','#4fa8ff','#b06eff','#ff5ec6','#ffd75e','#5eff8a','#ff7a5e','#ffffff'];
  const PALETTE_GOLD = ['#ffe9a8','#ffcf5e','#ffb23b','#fff2c9','#ffffff'];
  const PALETTE_MONO = ['#ffffff','#dfe8ff','#cfe0ff'];

  const root = document.documentElement.style;
  
  // Inject base64 SVGs into global CSS variables for the CSS classes to consume
  root.setProperty('--tex-stars-big',    buildSparkleSvg({seed:11, w:170, h:170, count:26, sizeMin:4,   sizeMax:9,   palette:PALETTE_FULL, starRatio:0.75}));
  root.setProperty('--tex-dust-small',   buildSparkleSvg({seed:22, w:90,  h:90,  count:34, sizeMin:1.4, sizeMax:3.2, palette:PALETTE_FULL, starRatio:0.25}));
  root.setProperty('--tex-stars-gold',   buildSparkleSvg({seed:33, w:130, h:130, count:20, sizeMin:3,   sizeMax:7,   palette:PALETTE_GOLD, starRatio:0.7}));
  root.setProperty('--tex-stars-rainbow',buildSparkleSvg({seed:44, w:100, h:100, count:30, sizeMin:2.5, sizeMax:6,   palette:PALETTE_FULL, starRatio:0.6}));
  root.setProperty('--tex-dust-mono',    buildSparkleSvg({seed:55, w:80,  h:80,  count:30, sizeMin:1.2, sizeMax:3,   palette:PALETTE_MONO, starRatio:0.2}));
}

/* ==========================================================================
   3. 3D POINTER TRACKING LOGIC
   ========================================================================== */

// Attach tracking events to a specific card element
function bindHoloCard(card) {
  // Prevent double-binding
  if (card.dataset.holoBound === "true") return;
  card.dataset.holoBound = "true";

  function update(clientX, clientY) {
    const rect = card.getBoundingClientRect();
    
    // Calculate pointer position as a percentage (0 to 100)
    const px = Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100));
    const py = Math.min(100, Math.max(0, ((clientY - rect.top) / rect.height) * 100));
    
    // Calculate center-based coordinates for rotation mechanics (-50 to 50)
    const cx = px - 50;
    const cy = py - 50;
    const edge = Math.min(1, Math.sqrt(cx * cx + cy * cy) / 70);

    // Inject dynamic values directly into the card's inline variables
    card.style.setProperty('--px', px + '%');
    card.style.setProperty('--py', py + '%');
    card.style.setProperty('--dx', px + '%');
    card.style.setProperty('--dy', py + '%');
    card.style.setProperty('--edge', edge.toFixed(2));
    
    // Calculate and apply 3D rotation limits (max 14 degrees)
    card.style.setProperty('--rot-x', (-(cy / 50) * 14) + 'deg');
    card.style.setProperty('--rot-y', ((cx / 50) * 14) + 'deg');
    
    // Disable transition on movement to ensure immediate tracking without lag
    card.style.transition = 'box-shadow 0.4s ease';
  }

  card.addEventListener('pointermove', (e) => update(e.clientX, e.clientY));
  
  card.addEventListener('pointerleave', () => {
    // Restore smooth transition for the snap-back animation
    card.style.transition = 'transform 0.55s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.4s ease';
    
    // Reset properties to default resting state
    card.style.setProperty('--rot-x', '0deg');
    card.style.setProperty('--rot-y', '0deg');
    card.style.setProperty('--dx', '50%');
    card.style.setProperty('--dy', '50%');
    card.style.setProperty('--edge', '0');
  });
}

// Auto-initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  // 1. Generate base SVG texture variables
  initializeHoloTextures();
  
  // 2. Bind existing cards on the page (if any exist on load)
  document.querySelectorAll('.holo-card').forEach(bindHoloCard);
});

// Expose the binding function globally for dynamically injected cards (e.g. via API)
window.PokyudexHolo = {
  bindCard: bindHoloCard,
  initTextures: initializeHoloTextures
};