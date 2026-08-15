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
        <button class="modal-close" onclick="document.getElementById('about-modal').style.display='none'">&times;</button>
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
        <button class="modal-close" onclick="document.getElementById('avatar-modal').style.display='none'">&times;</button>
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

function createCustomColorPicker(container, hiddenInputId, defaultColor) {
  if (!container) return null;
  const input = document.getElementById(hiddenInputId);
  if (!input) return null;
  let color = input.value || defaultColor || '#4f8bf9';
  let hsl = hexToHsl(color);
  let originalColor = color; 

  container.className = 'custom-color-picker-container';
  container.innerHTML = `<div class="color-swatch-btn" style="background-color: ${color}"></div>`;
  const swatchBtn = container.querySelector('.color-swatch-btn');

  // CREAZIONE PULITA HTML, SENZA STILI INLINE CONFLITTUALI
  const modalWrapper = document.createElement('div');
  modalWrapper.className = 'color-picker-modal-wrapper';
  
  modalWrapper.innerHTML = `
    <div class="color-picker-backdrop"></div>
    <div class="color-picker-dialog">
      <button class="cp-size-toggle-btn" title="Toggle Full Page" type="button">⤢</button>
      
      <div class="color-picker-wheel-zone">
        <div class="color-wheel">
          <div class="color-wheel-saturation"></div>
          <div class="color-wheel-lightness"></div>
          <div class="color-wheel-marker"></div>
        </div>
      </div>
      
      <div class="slider-group">
        <label>Lightness <span class="l-val">${hsl.l}%</span></label>
        <input type="range" class="cp-light" min="0" max="100" value="${hsl.l}">
      </div>
      
      <input type="text" class="color-picker-live-preview" value="${color.toUpperCase()}" maxlength="7">
      
      <button type="button" class="btn btn-accent cp-done-btn">SAVE & CLOSE</button>
      
      <div class="color-picker-saved-container">
        <div class="color-picker-saved-headline">
          <span>Saved Colors</span>
          <a class="save-current-color-btn">+ Save Current</a>
        </div>
        <div class="color-picker-saved-slots"></div>
      </div>
    </div>
  `;
  document.body.appendChild(modalWrapper);

  const dialog = modalWrapper.querySelector('.color-picker-dialog');
  const backdrop = modalWrapper.querySelector('.color-picker-backdrop');
  const wheel = modalWrapper.querySelector('.color-wheel');
  const marker = modalWrapper.querySelector('.color-wheel-marker');
  const lightSlider = modalWrapper.querySelector('.cp-light');
  const lValSpan = modalWrapper.querySelector('.l-val');
  const livePreviewInput = modalWrapper.querySelector('.color-picker-live-preview');
  const savedSlotsContainer = modalWrapper.querySelector('.color-picker-saved-slots');
  const saveBtn = modalWrapper.querySelector('.save-current-color-btn');
  const sizeToggleBtn = modalWrapper.querySelector('.cp-size-toggle-btn');
  const doneBtn = modalWrapper.querySelector('.cp-done-btn');

  let isDraggingWheel = false;

  // APERTURA: SALVIAMO IL COLORE INIZIALE E FORZIAMO LUM 50% SULLA RUOTA
  swatchBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    originalColor = input.value; 
    document.querySelectorAll('.color-picker-modal-wrapper').forEach(w => w.style.display = 'none');
    modalWrapper.style.display = 'flex';
    
    hsl.l = 50; 
    lightSlider.value = 50;
    updateMarkerPosition(hsl.h, hsl.s);
    updateColor();
    renderSavedColors();
  });

  // CHIUSURA: CONFERMIAMO IL COLORE E CHIUDIAMO CORRETTAMENTE L'ESPANSIONE
  doneBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    modalWrapper.style.display = 'none';
    dialog.classList.remove('expanded');
    sizeToggleBtn.textContent = '⤢';
  });

  // ANNULLAMENTO: CLICCANDO FUORI, RIPRISTINIAMO IL COLORE INIZIALE ESATTO
  backdrop.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    pickerInstance.setValue(originalColor);
    updateColor();
    modalWrapper.style.display = 'none';
    dialog.classList.remove('expanded');
    sizeToggleBtn.textContent = '⤢';
  });

  dialog.addEventListener('click', (e) => e.stopPropagation());
  dialog.addEventListener('mousedown', (e) => e.stopPropagation());
  dialog.addEventListener('touchstart', (e) => e.stopPropagation(), { passive: true });

  function updateMarkerPosition(h, s) {
    let currentWidth = wheel.offsetWidth;
    // Se è nascosto, width è 0, calcoliamo approssimativamente il raggio base o espanso
    if (currentWidth === 0) {
      currentWidth = dialog.classList.contains('expanded') ? Math.min(350, window.innerWidth * 0.7) : 200;
    }
    const r = currentWidth / 2;
    const angleRad = (h - 90) * (Math.PI / 180);
    const dist = (s / 100) * r;
    const x = r + dist * Math.cos(angleRad);
    const y = r + dist * Math.sin(angleRad);
    marker.style.left = `${x}px`;
    marker.style.top = `${y}px`;
  }

  // ESPANSIONE: USA SOLO LA CLASSE CSS PULITA
  sizeToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dialog.classList.toggle('expanded');
    const isExpanded = dialog.classList.contains('expanded');
    sizeToggleBtn.textContent = isExpanded ? '✕' : '⤢';
    setTimeout(() => updateMarkerPosition(hsl.h, hsl.s), 10);
  });

  livePreviewInput.addEventListener('change', () => {
    let inputVal = livePreviewInput.value.trim();
    if (!inputVal.startsWith('#')) { inputVal = '#' + inputVal; }
    if (/^#[0-9A-F]{6}$/i.test(inputVal)) {
      pickerInstance.setValue(inputVal);
      updateColor();
    } else {
      livePreviewInput.value = input.value.toUpperCase();
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
    hsl.l = 50;
    lightSlider.value = 50;
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
    
    let overlayColor = 'transparent';
    if (hsl.l < 50) {
      let opacity = (50 - hsl.l) / 50;
      overlayColor = `rgba(0, 0, 0, ${opacity})`;
    } else if (hsl.l > 50) {
      let opacity = (hsl.l - 50) / 50;
      overlayColor = `rgba(255, 255, 255, ${opacity})`;
    }
    wheel.style.setProperty('--cp-overlay', overlayColor);
    
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
      
      let overlayColor = 'transparent';
      if (hsl.l < 50) {
        let opacity = (50 - hsl.l) / 50;
        overlayColor = `rgba(0, 0, 0, ${opacity})`;
      } else if (hsl.l > 50) {
        let opacity = (hsl.l - 50) / 50;
        overlayColor = `rgba(255, 255, 255, ${opacity})`;
      }
      wheel.style.setProperty('--cp-overlay', overlayColor);
      
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

// ==========================================================================
// PREMIUM V3 HOLO GLOBAL CARD SYSTEM
// ==========================================================================
function initGlobalCardModal() {
  if (document.getElementById('global-card-modal')) return;

  const modalHtml = `
    <div id="global-card-modal" style="display:none; position:fixed; inset:0; z-index:99999; background:rgba(8,7,12,0.94); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); align-items:center; justify-content:center; box-sizing:border-box; padding:40px; transition: opacity 0.2s ease;">
      <div class="global-modal-backdrop" style="position:absolute; inset:0; cursor:zoom-out;"></div>
      <div class="global-card-transform-container" style="position:relative; z-index:1; display:flex; flex-direction:column; align-items:center; max-width:90vw;">
        <button class="modal-close" style="position:absolute; top:-18px; right:-18px; width:36px; height:36px; border-radius:50%; background:#1c1a25; border:1px solid #322f3d; color:#fff; font-size:20px; line-height:1; cursor:pointer; display:flex; align-items:center; justify-content:center; z-index:100;">&times;</button>
        
        <div class="card-wrap" style="perspective:1200px; width:460px; max-width:90vw; aspect-ratio:63/88;">
          <div class="holo-card" id="global-holo-card">
            <img class="global-modal-img art" src="" alt="Card View" />
            <div class="layer glare"></div>
          </div>
        </div>

        <div class="modal-card-info" style="text-align:center; margin-top:24px; pointer-events:none;">
          <div class="global-modal-name" style="font-family:'Rajdhani',sans-serif; font-size:26px; font-weight:700; color:#ece8e2;"></div>
          <div class="global-modal-set" style="font-family:'JetBrains Mono',monospace; color:var(--teal); font-size:14px; margin-top:4px; display:inline-block; transition: color 0.2s ease;"></div>
          <div class="global-modal-rarity" style="font-family:'JetBrains Mono',monospace; color:var(--text-muted); font-size:12px; margin-top:2px;"></div>
          <div class="global-modal-price" style="font-family:'JetBrains Mono',monospace; color:#f0b93d; font-size:16px; margin-top:8px;"></div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const modal = document.getElementById('global-card-modal');
  const backdrop = modal.querySelector('.global-modal-backdrop');
  const closeBtn = modal.querySelector('.modal-close');
  const holoCard = document.getElementById('global-holo-card');

  function resetPosition() {
    holoCard.style.transition = 'none';
    holoCard.style.setProperty('--rot-x', '0deg');
    holoCard.style.setProperty('--rot-y', '0deg');
    holoCard.style.setProperty('--dx', '50%');
    holoCard.style.setProperty('--dy', '50%');
    holoCard.style.setProperty('--edge', '0');
    holoCard.style.setProperty('--px', '50%');
    holoCard.style.setProperty('--py', '50%');
  }

  let isTicking = false;

  function handleCardTilt(clientX, clientY) {
    if (!isTicking) {
      window.requestAnimationFrame(() => {
        const rect = holoCard.getBoundingClientRect();
        if (rect.width !== 0 && rect.height !== 0) {
          const px = Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100));
          const py = Math.min(100, Math.max(0, ((clientY - rect.top) / rect.height) * 100));
          const cx = px - 50;
          const cy = py - 50;
          const edge = Math.min(1, Math.sqrt(cx * cx + cy * cy) / 70);

          holoCard.style.setProperty('--px', px + '%');
          holoCard.style.setProperty('--py', py + '%');
          holoCard.style.setProperty('--dx', px + '%');
          holoCard.style.setProperty('--dy', py + '%');
          holoCard.style.setProperty('--edge', edge.toFixed(2));
          holoCard.style.setProperty('--rot-x', (-(cy / 50) * 20) + 'deg');
          holoCard.style.setProperty('--rot-y', ((cx / 50) * 20) + 'deg');
          holoCard.style.transition = 'none';
        }
        isTicking = false;
      });
      isTicking = true;
    }
  }

  modal.addEventListener('mousemove', (e) => {
    if (modal.style.display === 'none') return;
    handleCardTilt(e.clientX, e.clientY);
  });

  modal.addEventListener('touchmove', (e) => {
    if (modal.style.display === 'none') return;
    e.preventDefault(); 
    if (e.touches && e.touches.length > 0) {
      handleCardTilt(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: false });

  modal.addEventListener('touchstart', (e) => {
    if (modal.style.display === 'none') return;
    if (e.touches && e.touches.length > 0) {
      handleCardTilt(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: true });

  backdrop.addEventListener('click', hideModal);
  closeBtn.addEventListener('click', hideModal);

  function hideModal() {
    modal.style.opacity = '0';
    setTimeout(() => {
      modal.style.display = 'none';
      resetPosition();
    }, 200); 
  }

  window.openGlobalCardModal = function(cardOrName, imageUrl, priceLabel, rarityStr) {
    let card = {};
    if (typeof cardOrName === 'string') {
      card = { name: cardOrName, rarity: rarityStr };
    } else {
      card = cardOrName || {};
    }
    
    const imgTarget = imageUrl || card.image_large || card.image_small || '';
    const priceTarget = priceLabel || (card.price_market ? formatPrice(card.price_market, card.currency) : 'n/a');
    const setTarget = card.set_name || (card.set && card.set.name) || '';
    const setIdTarget = card.set_id || (card.set && card.set.id) || '';
    const rarityTarget = rarityStr || card.rarity || '';

    document.querySelector('.global-modal-img').src = imgTarget;
    document.querySelector('.global-modal-name').textContent = card.name || cardOrName || 'Custom Divider / Artwork';
    
    const setEl = document.querySelector('.global-modal-set');
    if (setEl) {
      setEl.textContent = setTarget;
      setEl.style.display = setTarget ? 'inline-block' : 'none';
      setEl.style.pointerEvents = 'auto'; // Rende cliccabile il set nonostante pointer-events: none del contenitore padre
      
      if (setIdTarget && card.id) {
        setEl.style.cursor = 'pointer';
        setEl.onmouseover = () => { setEl.style.textDecoration = 'underline'; };
        setEl.onmouseout = () => { setEl.style.textDecoration = 'none'; };
        setEl.onclick = (e) => {
          e.stopPropagation();
          window.location.href = `set.html?id=${encodeURIComponent(setIdTarget)}&focus=${encodeURIComponent(card.id)}`;
        };
      } else {
        setEl.style.cursor = 'default';
        setEl.style.textDecoration = 'none';
        setEl.onmouseover = null;
        setEl.onmouseout = null;
        setEl.onclick = null;
      }
    }

    const rarityEl = document.querySelector('.global-modal-rarity');
    if (rarityEl) {
      rarityEl.textContent = rarityTarget;
      rarityEl.style.display = rarityTarget ? 'block' : 'none';
    }

    document.querySelector('.global-modal-price').textContent = priceTarget;

    const transformContainer = modal.querySelector('.global-card-transform-container');
    transformContainer.style.transition = 'none';
    transformContainer.style.transform = 'perspective(1200px) scale(0.95)';
    
    modal.style.opacity = '0';
    modal.style.display = 'flex';
    
    requestAnimationFrame(() => {
      modal.style.opacity = '1';
      transformContainer.style.transition = 'transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)';
      transformContainer.style.transform = 'perspective(1200px) scale(1)';
    });
  };
}

// ==========================================================================
// SCROLL TO TOP FLOATING BUTTON
// ==========================================================================
function initScrollToTopButton() {
  if (document.getElementById('scroll-to-top-btn')) return;

  const btn = document.createElement('button');
  btn.id = 'scroll-to-top-btn';
  btn.innerHTML = '▲';
  btn.title = 'Torna in alto';
  btn.style.cssText = `
    position: fixed;
    bottom: 24px; 
    right: 24px;  
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--gold);
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    z-index: 1150;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s ease, visibility 0.2s ease, transform 0.15s ease, border-color 0.15s ease;
  `;

  btn.onmouseover = () => { btn.style.borderColor = 'var(--gold)'; btn.style.transform = 'scale(1.08)'; };
  btn.onmouseout = () => { btn.style.borderColor = 'var(--border)'; btn.style.transform = 'scale(1)'; };
  btn.onclick = () => { window.scrollTo({ top: 0, behavior: 'smooth' }); };

  document.body.appendChild(btn);

  window.addEventListener('scroll', () => {
    if (window.scrollY > 300) {
      btn.style.opacity = '1';
      btn.style.visibility = 'visible';
    } else {
      btn.style.opacity = '0';
      btn.style.visibility = 'hidden';
    }
  }, { passive: true });
}

document.addEventListener('DOMContentLoaded', () => {
  initGlobalCardModal();
  initScrollToTopButton();
});
if (document.body) { 
  initGlobalCardModal(); 
  initScrollToTopButton();
} else { 
  window.addEventListener('load', () => {
    initGlobalCardModal();
    initScrollToTopButton();
  }); 
}

document.addEventListener('click', () => {
  document.querySelectorAll('.color-picker-dropdown.active').forEach(d => {
    d.classList.remove('active');
    d.classList.remove('expanded');
    const toggle = d.querySelector('.cp-size-toggle-btn');
    if(toggle) toggle.textContent = '⤢';
  });
});

window.isDraggingCard = false;
document.addEventListener('dragstart', () => { window.isDraggingCard = true; });
document.addEventListener('dragend', () => { window.isDraggingCard = false; });
document.addEventListener('drop', () => { window.isDraggingCard = false; });
window.addEventListener('wheel', (e) => { if (window.isDraggingCard) window.scrollBy(0, e.deltaY); }, { passive: true });