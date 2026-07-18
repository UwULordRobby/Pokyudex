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

function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function requireAuth() {
  try {
    const data = await api('/api/me');
    if (!data.user) {
      window.location.href = 'login.html';
      return null;
    }
    const nameEl = document.getElementById('current-username');
    if (nameEl) nameEl.textContent = data.user.username || data.user.email;
    renderUserAvatar(data.user);
    return data.user;
  } catch (err) {
    window.location.href = 'login.html';
    return null;
  }
}

function renderBloomLayer(palette) {
  if (!palette || !palette.length) return;
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  const isSetPage = window.location.pathname.includes('set.html') || new URLSearchParams(window.location.search).has('id');

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
        s = clamp(s + 30, 85, 100);  
        l = clamp(l + 10, 52, 72);   
        alpha = 0.95;                
      } else if (paletteIndex === 1) {
        s = clamp(s + 20, 75, 95);
        l = clamp(l + 6, 48, 68);
        alpha = 0.85;
      } else {
        s = clamp(s + 15, 60, 85);  
        l = clamp(l + 8, 42, 60);   
        alpha = 0.75;               
      }
    } else {
      s = clamp(s - 15, 15, 55);
      l = clamp(l - 15, 18, 55);
      alpha = 0.4;
    }

    const leftVal = randomRange(-20, 95);
    const topVal = isSetPage ? randomRange(-15, 60) : randomRange(30, 80);

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
    blobElement.style.background = `radial-gradient(circle at center, 
      hsla(${h}, ${s}%, ${l}%, ${alpha}) 0%, 
      hsla(${h}, ${s}%, ${l}%, ${alpha * 0.35}) 55%, 
      transparent 100%
    )`;
    bloom.appendChild(blobElement);
  }
}

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

const GEN1_NAMES = ["Bulbasaur","Ivysaur","Venusaur","Charmander","Charmeleon","Charizard","Squirtle","Wartortle","Blastoise","Caterpie","Metapod","Butterfree","Weedle","Kakuna","Beedrill","Pidgey","Pidgeotto","Pidgeot","Rattata","Raticate","Spearow","Fearow","Ekans","Arbok","Pikachu","Raichu","Sandshrew","Sandslash","Nidoran♀","Nidorina","Nidoqueen","Nidoran♂","Nidorino","Nidoking","Clefairy","Clefable","Vulpix","Ninetales","Jigglypuff","Wigglytuff","Zubat","Golbat","Oddish","Gloom","Vileplume","Paras","Parasect","Venonat","Venomoth","Diglett","Dugtrio","Meowth","Persian","Psyduck","Golduck","Mankey","Primeape","Growlithe","Arcanine","Poliwag","Poliwhirl","Poliwrath","Abra","Kadabra","Alakazam","Machop","Machoke","Machamp","Bellsprout","Weepinbell","Victreebel","Tentacool","Tentacruel","Geodude","Graveler","Golem","Ponyta","Rapidash","Slowpoke","Slowbro","Magnemite","Magneton","Farfetch'd","Doduo","Dodrio","Seel","Dewgong","Grimer","Muk","Shellder","Cloyster","Gastly","Haunter","Gengar","Onix","Drowzee","Hypno","Krabby","Kingler","Voltorb","Electrode","Exeggcute","Exeggutor","Cubone","Marowak","Hitmonlee","Hitmonchan","Lickitung","Koffing","Weezing","Rhyhorn","Rhydon","Chansey","Tangela","Kangaskhan","Horsea","Seadra","Goldeen","Seaking","Staryu","Starmie","Mr. Mime","Scyther","Jynx","Electabuzz","Magmar","Pinsir","Tauros","Magikarp","Gyarados","Lapras","Ditto","Eevee","Vaporeon","Jolteon","Flareon","Porygon","Omanyte","Omastar","Kabuto","Kabutops","Aerodactyl","Snorlax","Articuno","Zapdos","Moltres","Dratini","Dragonair","Dragonite","Mewtwo","Mew"];
const AVATAR_OPTIONS = [
  ...GEN1_NAMES.map((name, idx) => ({ id: idx + 1, name })),
  { id: 196, name: "Espeon" }, { id: 197, name: "Umbreon" },
  { id: 470, name: "Leafeon" }, { id: 471, name: "Glaceon" },
  { id: 700, name: "Sylveon" }, { id: 778, name: "Mimikyu" },
];

function avatarSpriteUrl(pokemonId) {
  return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${pokemonId}.png`;
}

let currentUserForAvatar = null;
function renderUserAvatar(user) {
  currentUserForAvatar = user;
  const usernameEl = document.getElementById('current-username');
  if (!usernameEl || !usernameEl.parentElement) return;
  let btn = document.getElementById('user-avatar-btn');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'user-avatar-btn';
    btn.className = 'avatar-btn';
    btn.title = 'Change profile avatar';
    btn.onclick = showAvatarPickerModal;
    usernameEl.parentElement.insertBefore(btn, usernameEl);
  }
  const id = user && user.avatar_pokemon_id;
  btn.innerHTML = id
    ? `<img src="${avatarSpriteUrl(id)}" alt="Avatar" onerror="this.style.display='none'">`
    : `<span class="avatar-placeholder">?</span>`;
}

function showAvatarPickerModal() {
  let modal = document.getElementById('avatar-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'avatar-modal';
    modal.className = 'modal';
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
    const grid = AVATAR_OPTIONS.map(p => `
      <div class="avatar-option" data-id="${p.id}" title="${escapeHtml(p.name)}">
        <img src="${avatarSpriteUrl(p.id)}" alt="${escapeHtml(p.name)}" loading="lazy">
        <span>${escapeHtml(p.name)}</span>
      </div>
    `).join('');
    modal.innerHTML = `
      <div class="about-card" style="max-width:560px; max-height:80vh; overflow-y:auto;" onclick="event.stopPropagation()">
        <button class="modal-close" style="position:absolute; top:-14px; right:-14px; width:32px; height:32px; border-radius:50%; background:var(--panel); border:1px solid var(--border); font-size:18px;" onclick="document.getElementById('avatar-modal').style.display='none'">&times;</button>
        <div class="auth-brand" style="justify-content:flex-start; margin-bottom:14px;"><span class="dot"></span> Choose Your Profile Avatar</div>
        <div class="avatar-grid">${grid}</div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('.avatar-option').forEach(el => {
      el.addEventListener('click', async () => {
        const id = parseInt(el.dataset.id);
        try {
          await api('/api/me/avatar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pokemon_id: id })
          });
          if (currentUserForAvatar) currentUserForAvatar.avatar_pokemon_id = id;
          renderUserAvatar(currentUserForAvatar);
          modal.style.display = 'none';
        } catch (err) { alert(err.message); }
      });
    });
  }
  modal.style.display = 'flex';
}

async function logoutUser() {
  try { await api('/api/logout', { method: 'POST' }); } catch (err) {}
  window.location.href = 'login.html';
}

function hexToHsl(hex) {
  hex = hex.replace(/^#/, '');
  if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  let r = parseInt(hex.substring(0, 2), 16) / 255;
  let g = parseInt(hex.substring(2, 4), 16) / 255;
  let b = parseInt(hex.substring(4, 6), 16) / 255;
  let max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  if (max === min) { h = s = 0; } else {
    let d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  let c = (1 - Math.abs(2 * l - 1)) * s;
  let x = c * (1 - Math.abs((h / 60) % 2 - 1));
  let m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (0 <= h && h < 60) { r = c; g = x; b = 0; }
  else if (60 <= h && h < 120) { r = x; g = c; b = 0; }
  else if (120 <= h && h < 180) { r = 0; g = c; b = x; }
  else if (180 <= h && h < 240) { r = 0; g = x; b = c; }
  else if (240 <= h && h < 300) { r = x; g = 0; b = c; }
  else if (300 <= h && h < 360) { r = c; g = 0; b = x; }
  let rHex = Math.round((r + m) * 255).toString(16).padStart(2, '0');
  let gHex = Math.round((g + m) * 255).toString(16).padStart(2, '0');
  let bHex = Math.round((b + m) * 255).toString(16).padStart(2, '0');
  return `#${rHex}${gHex}${bHex}`;
}

// 100% CALIBRATED CHROMATIC WHEEL WITH 10 SAVED COLOR HISTORIES AND PASTE HEX CODE INPUT TWEAK
function createCustomColorPicker(container, hiddenInputId, defaultColor) {
  if (!container) return null;
  const input = document.getElementById(hiddenInputId);
  if (!input) return null;
  let color = input.value || defaultColor || '#ffffff';
  let hsl = hexToHsl(color);

  container.className = 'custom-color-picker-container';
  container.innerHTML = `
    <div class="color-swatch-btn" style="background-color: ${color}"></div>
    <div class="color-picker-dropdown">
      <button class="cp-size-toggle-btn" title="Toggle Full Page" type="button">⤢</button>
      <div class="color-picker-wheel-zone">
        <div class="color-wheel">
          <div class="color-wheel-saturation"></div>
          <div class="color-wheel-marker"></div>
        </div>
      </div>
      <div class="slider-group" style="margin-top: 14px;">
        <label>Lightness: <span class="l-val">${hsl.l}%</span></label>
        <input type="range" class="cp-light" min="0" max="100" value="${hsl.l}">
      </div>
      <!-- TWEAK: Live preview converted to input text tag to allow copy/pasting hex codes -->
      <input type="text" class="color-picker-live-preview" value="${color.toUpperCase()}" maxlength="7" style="background-color: ${color}; color: ${hsl.l > 50 ? '#121118' : '#ece8e2'}">
      <div class="color-picker-saved-container">
        <div class="color-picker-saved-headline">
          <span>Saved Colors</span>
          <a class="save-current-color-btn" style="color:var(--teal); cursor:pointer; font-size:10px;">+ Save Current</a>
        </div>
        <div class="color-picker-saved-slots"></div>
      </div>
    </div>
  `;

  const swatchBtn = container.querySelector('.color-swatch-btn');
  const dropdown = container.querySelector('.color-picker-dropdown');
  const wheel = container.querySelector('.color-wheel');
  const marker = container.querySelector('.color-wheel-marker');
  const lightSlider = container.querySelector('.cp-light');
  const lValSpan = container.querySelector('.l-val');
  const livePreviewInput = container.querySelector('.color-picker-live-preview');
  const savedSlotsContainer = container.querySelector('.color-picker-saved-slots');
  const saveBtn = container.querySelector('.save-current-color-btn');
  const sizeToggleBtn = container.querySelector('.cp-size-toggle-btn');

  let isDraggingWheel = false;

  swatchBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    document.querySelectorAll('.color-picker-dropdown.active').forEach(d => {
      if (d !== dropdown) {
        d.classList.remove('active');
        d.classList.remove('expanded');
      }
    });
    dropdown.classList.toggle('active');
    if (dropdown.classList.contains('active')) {
      updateMarkerPosition(hsl.h, hsl.s);
      renderSavedColors();
    }
  });

  dropdown.addEventListener('click', (e) => { e.stopPropagation(); });

  function updateMarkerPosition(h, s) {
    let currentWidth = wheel.offsetWidth;
    if (currentWidth === 0) {
      currentWidth = dropdown.classList.contains('expanded') ? 320 : 130;
    }
    const r = currentWidth / 2;
    const angleRad = (h - 90) * (Math.PI / 180);
    const dist = (s / 100) * r;
    const x = r + dist * Math.cos(angleRad);
    const y = r + dist * Math.sin(angleRad);
    marker.style.left = `${x}px`;
    marker.style.top = `${y}px`;
  }

  sizeToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('expanded');
    sizeToggleBtn.textContent = dropdown.classList.contains('expanded') ? '✕' : '⤢';
    setTimeout(() => { updateMarkerPosition(hsl.h, hsl.s); }, 10);
  });

  /* NEW TWEAK: Add event listener to process manual color code entries and pastes */
  livePreviewInput.addEventListener('change', () => {
    let inputVal = livePreviewInput.value.trim();
    if (!inputVal.startsWith('#')) { inputVal = '#' + inputVal; }
    if (/^#[0-9A-F]{6}$/i.test(inputVal)) {
      pickerInstance.setValue(inputVal);
      updateColor();
    } else {
      livePreviewInput.value = input.value.toUpperCase(); // Restore on typing fault
    }
  });
  livePreviewInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') livePreviewInput.blur(); });

  function handleWheelEvent(e) {
    const rect = wheel.getBoundingClientRect();
    const r = rect.width / 2;
    const dx = e.clientX - (rect.left + r);
    const dy = e.clientY - (rect.top + r);
    
    let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
    if (angle < 0) angle += 360;
    if (angle >= 360) angle -= 360;
    
    const dist = Math.sqrt(dx*dx + dy*dy);
    const s = Math.min(100, Math.round((dist / r) * 100));
    
    hsl.h = Math.round(angle);
    hsl.s = s;

    updateMarkerPosition(hsl.h, hsl.s);
    updateColor();
  }

  wheel.addEventListener('pointerdown', (e) => {
    isDraggingWheel = true;
    wheel.setPointerCapture(e.pointerId);
    handleWheelEvent(e);
  });

  wheel.addEventListener('pointermove', (e) => { if (isDraggingWheel) handleWheelEvent(e); });
  wheel.addEventListener('pointerup', (e) => {
    isDraggingWheel = false;
    try { wheel.releasePointerCapture(e.pointerId); } catch(err) {}
  });

  function updateColor() {
    hsl.l = parseInt(lightSlider.value);
    lValSpan.textContent = hsl.l + '%';
    const hex = hslToHex(hsl.h, hsl.s, hsl.l);
    input.value = hex;
    swatchBtn.style.backgroundColor = hex;
    
    if (livePreviewInput) {
      livePreviewInput.value = hex.toUpperCase();
      livePreviewInput.style.backgroundColor = hex;
      livePreviewInput.style.color = hsl.l > 50 ? '#121118' : '#ece8e2';
    }
    
    input.dispatchEvent(new Event('change'));
    input.dispatchEvent(new Event('input'));
  }

  lightSlider.addEventListener('input', updateColor);

  function getSavedColors() {
    try {
      const raw = localStorage.getItem('pokyudex_saved_colors');
      return raw ? JSON.parse(raw) : ['#1c1a25', '#16141d', '#a855f7', '#4f8bf9', '#f472b6', '#4fd8c4', '#f0b93d', '#e06565'];
    } catch(e) { return []; }
  }

  function saveColorToHistory(hex) {
    let colors = getSavedColors();
    colors = colors.filter(c => c.toLowerCase() !== hex.toLowerCase());
    colors.unshift(hex);
    if (colors.length > 10) colors = colors.slice(0, 10);
    localStorage.setItem('pokyudex_saved_colors', JSON.stringify(colors));
    renderSavedColors();
  }

  function renderSavedColors() {
    savedSlotsContainer.innerHTML = '';
    const colors = getSavedColors();
    for (let i = 0; i < 10; i++) {
      const slot = document.createElement('div');
      slot.className = 'saved-color-slot';
      if (colors[i]) {
        slot.classList.add('filled');
        slot.style.backgroundColor = colors[i];
        slot.title = colors[i].toUpperCase();
        slot.addEventListener('click', (e) => {
          e.stopPropagation();
          pickerInstance.setValue(colors[i]);
          updateColor();
        });
      }
      savedSlotsContainer.appendChild(slot);
    }
  }

  saveBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    saveColorToHistory(input.value);
  });

  const pickerInstance = {
    setValue: function(hex) {
      input.value = hex;
      swatchBtn.style.backgroundColor = hex;
      hsl = hexToHsl(hex);
      lightSlider.value = hsl.l;
      lValSpan.textContent = hsl.l + '%';
      updateMarkerPosition(hsl.h, hsl.s);
      
      if (livePreviewInput) {
        livePreviewInput.value = hex.toUpperCase();
        livePreviewInput.style.backgroundColor = hex;
        livePreviewInput.style.color = hsl.l > 50 ? '#121118' : '#ece8e2';
      }
    }
  };

  return pickerInstance;
}

document.addEventListener('click', () => {
  document.querySelectorAll('.color-picker-dropdown.active').forEach(d => {
    d.classList.remove('active');
    d.classList.remove('expanded');
  });
});

window.isDraggingCard = false;
document.addEventListener('dragstart', () => { window.isDraggingCard = true; });
document.addEventListener('dragend', () => { window.isDraggingCard = false; });
document.addEventListener('drop', () => { window.isDraggingCard = false; });
window.addEventListener('wheel', (e) => { if (window.isDraggingCard) window.scrollBy(0, e.deltaY); }, { passive: true });