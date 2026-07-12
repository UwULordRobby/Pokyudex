async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !path.startsWith('/api/login') && !path.startsWith('/api/register') && !path.startsWith('/api/me')) {
    window.location.href = 'login.html';
    throw new Error('Session expired, please sign in again.');
  }
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function formatPrice(value, currency) {
  if (value === null || value === undefined) return null;
  const symbol = currency === 'EUR' ? '\u20ac' : '$';
  return symbol + Number(value).toFixed(2);
}

// Escapes text before inserting it into innerHTML templates, so that a
// card/set name containing HTML-special characters can never be
// interpreted as markup or break out of an attribute. Always wrap any
// value coming from the API (or from any external source) with this
// before interpolating it into an innerHTML template string.
function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Checks whether a user is logged in. Redirects to login.html if not.
// Call this at the top of every protected page, before loading any data.
async function requireAuth() {
  try {
    const data = await api('/api/me');
    if (!data.user) {
      window.location.href = 'login.html';
      return null;
    }
    const nameEl = document.getElementById('current-username');
    if (nameEl) nameEl.textContent = data.user.username || data.user.email;
    return data.user;
  } catch (err) {
    window.location.href = 'login.html';
    return null;
  }
}

// Renders (or updates) the page's "bloom" background: a handful of
// blob-shaped radial gradients built from the given list of HSL colors
// ({h, s, l} objects, 0-360 / 0-100 / 0-100). Shared by every page that
// wants a themed glow — pages with a fixed dot color pass a small fixed
// palette built around that hue; set.html passes the palette it
// extracted from the priciest card's artwork instead. The actual visual
// tuning (blur, fade shape, drift animation) lives in style.css.
function renderBloomLayer(palette) {
  if (!palette || !palette.length) return;
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  const isSetPage = window.location.pathname.includes('set.html') || new URLSearchParams(window.location.search).has('id');

  // Iniezione del filtro SVG Gooey (immutato)
  if (!document.getElementById('gooey-svg-element')) {
    const svgFilter = `
      <svg id="gooey-svg-element" xmlns="http://www.w3.org/2000/svg" version="1.1" style="position:fixed; top:-100%; left:-100%; width:0; height:0; opacity:0; pointer-events:none; z-index:-9999;">
        <defs>
          <filter id="gooey-liquid">
            <feGaussianBlur in="SourceGraphic" stdDeviation="60" result="blur" />
            <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 11 -3.5" result="goo" />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
        </defs>
      </svg>
    `;
    document.body.insertAdjacentHTML('beforeend', svgFilter);
  }

  let bloom = document.getElementById('bloom-layer');
  if (!bloom) {
    bloom = document.createElement('div');
    bloom.id = 'bloom-layer';
    document.body.prepend(bloom);
  }
  
  bloom.innerHTML = '';

  const randomRange = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  const totalBlobs = 9; 

  for (let i = 0; i < totalBlobs; i++) {
    const paletteIndex = i % palette.length;
    const colorSrc = palette[paletteIndex];
    
    let h = colorSrc.h;
    let s = colorSrc.s;
    let l = colorSrc.l;
    let alpha = 0.75; 

    if (isSetPage) {
      if (paletteIndex === 0) {
        // Il colore più predominante della carta: accesissimo e saturo
        s = clamp(s + 30, 85, 100);  
        l = clamp(l + 10, 52, 72);   
        alpha = 0.95;                
      } else if (paletteIndex === 1) {
        // Il secondo colore più presente: vivido ma leggermente subordinato al primo
        s = clamp(s + 20, 75, 95);
        l = clamp(l + 6, 48, 68);
        alpha = 0.85;
      } else {
        // MODIFICA: Colori meno predominanti (terziari/quaternari)
        // Diamo un boost per accenderli ed evitare l'effetto affogato nel nero
        s = clamp(s + 15, 60, 85);  // Minimo garantito di saturazione al 60%
        l = clamp(l + 8, 42, 60);   // Portiamo la luminosità a valori visibili e brillanti
        alpha = 0.75;               // Incrementata l'opacità per renderli densi
      }
    } else {
      // Pagine principali: mantengono l'effetto morbido e desaturato per non stancare
      s = clamp(s - 15, 15, 55);
      l = clamp(l - 15, 18, 55);
      alpha = 0.4;
    }

    // Posizionamento fluido e dinamico su tutto lo schermo (incluso il centro)
    const leftVal = randomRange(-20, 95);
    const topVal = isSetPage ? randomRange(-15, 60) : randomRange(30, 80);

    // Misure asimmetriche (blob grandi alternati a scie strette)
    let widthVal, heightVal;
    if (i % 3 === 0) {
      widthVal = randomRange(20, 35);
      heightVal = randomRange(40, 60);
    } else {
      widthVal = randomRange(45, 65);
      heightVal = randomRange(65, 90);
    }

    const blobElement = document.createElement('div');
    blobElement.className = 'bloom-blob';
    
    blobElement.style.left = `${leftVal}%`;
    blobElement.style.top = `${topVal}%`;
    blobElement.style.width = `${widthVal}vw`;
    blobElement.style.height = `${heightVal}vh`;
    
    const motionIndex = (i % 4) + 1;
    blobElement.classList.add(`motion-${motionIndex}`);

    // Gradiente radiale fluido
    blobElement.style.background = `radial-gradient(circle at center, 
      hsla(${h}, ${s}%, ${l}%, ${alpha}) 0%, 
      hsla(${h}, ${s}%, ${l}%, ${alpha * 0.35}) 55%, 
      transparent 100%
    )`;
    
    bloom.appendChild(blobElement);
  }
}

// Shows a small "About the creator" modal with contact info. Built once
// and reused across pages (same pattern as the bloom layer): the first
// call injects the markup, later calls just toggle visibility.
// EDIT THE PLACEHOLDER VALUES BELOW WITH YOUR OWN CONTACT INFO.
function showAboutModal() {
  let modal = document.getElementById('about-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'about-modal';
    modal.className = 'modal';
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
    modal.innerHTML = `
      <div class="about-card">
        <button class="modal-close" style="position:absolute; top:-14px; right:-14px; width:32px; height:32px; border-radius:50%; background:var(--panel); border:1px solid var(--border); font-size:18px;" onclick="document.getElementById('about-modal').style.display='none'">&times;</button>
        <div class="auth-brand" style="justify-content:flex-start; margin-bottom:14px;"><span class="dot"></span> Pokyudex</div>
        <p style="color:var(--text-muted); font-size:14px; margin:0 0 18px;">Built with love for the Pokémon TCG community.</p>
        <div style="display:flex; flex-direction:column; gap:10px; font-family:'JetBrains Mono', monospace; font-size:13px;">
          <div>📧 &nbsp;your-email@example.com</div>
          <div>💬 &nbsp;Discord: your_handle</div>
          <div>🐙 &nbsp;github.com/your_handle</div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.style.display = 'flex';
}

async function logoutUser() {
  try {
    await api('/api/logout', { method: 'POST' });
  } catch (err) { /* ignore, redirect anyway */ }
  window.location.href = 'login.html';
}