<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Identificador de Conectores — FAE</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0e0f11;
    --surface: #16181c;
    --surface2: #1e2126;
    --border: #2a2d35;
    --border2: #363a44;
    --accent: #e8ff47;
    --accent2: #b8cc38;
    --text: #f0f2f5;
    --text2: #8a8f9e;
    --text3: #555a68;
    --red: #ff4d4d;
    --green: #4dff91;
    --blue: #4d9fff;
    --radius: 10px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* TOP BAR */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .logo-mark {
    width: 32px; height: 32px;
    background: var(--accent);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
  }

  .logo-mark svg { width: 18px; height: 18px; }

  .logo-text {
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    color: var(--text2);
    letter-spacing: 0.04em;
  }

  .logo-text span { color: var(--text); }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text3);
  }

  .status-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--green);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* MAIN LAYOUT */
  main {
    flex: 1;
    display: grid;
    grid-template-columns: 420px 1fr;
    gap: 0;
  }

  /* LEFT PANEL */
  .left-panel {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 28px 24px;
    gap: 24px;
  }

  .panel-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    color: var(--text3);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  /* UPLOAD ZONE */
  .upload-zone {
    border: 1.5px dashed var(--border2);
    border-radius: var(--radius);
    aspect-ratio: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    position: relative;
    overflow: hidden;
    background: var(--surface);
  }

  .upload-zone:hover {
    border-color: var(--accent);
    background: rgba(232, 255, 71, 0.03);
  }

  .upload-zone.dragover {
    border-color: var(--accent);
    background: rgba(232, 255, 71, 0.06);
  }

  .upload-zone.has-image {
    border-style: solid;
    border-color: var(--border2);
  }

  .upload-preview {
    position: absolute;
    inset: 0;
    object-fit: contain;
    padding: 16px;
    display: none;
  }

  .upload-zone.has-image .upload-preview { display: block; }
  .upload-zone.has-image .upload-placeholder { display: none; }

  .upload-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .upload-icon {
    width: 56px; height: 56px;
    border-radius: 14px;
    background: var(--surface2);
    border: 1px solid var(--border2);
    display: flex; align-items: center; justify-content: center;
  }

  .upload-icon svg { width: 24px; height: 24px; color: var(--text3); }

  .upload-hint {
    text-align: center;
  }

  .upload-hint p {
    font-size: 13px;
    color: var(--text2);
    line-height: 1.5;
  }

  .upload-hint .key {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text3);
    margin-top: 6px;
  }

  .upload-badge {
    position: absolute;
    top: 12px; right: 12px;
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 20px;
    padding: 4px 10px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text3);
    display: none;
  }

  .upload-zone.has-image .upload-badge { display: block; }

  .upload-actions {
    position: absolute;
    bottom: 12px;
    display: flex; gap: 8px;
    display: none;
  }

  .upload-zone.has-image .upload-actions { display: flex; }

  .btn-small {
    padding: 6px 12px;
    border-radius: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border2);
    background: var(--surface2);
    color: var(--text2);
    transition: all 0.15s;
  }

  .btn-small:hover { border-color: var(--border), ; color: var(--text); }

  /* DESCRIPCION */
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .field-label {
    font-size: 12px;
    color: var(--text2);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .optional-tag {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    color: var(--text3);
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 6px;
    letter-spacing: 0.06em;
  }

  textarea {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    line-height: 1.6;
    padding: 12px 14px;
    resize: none;
    height: 80px;
    transition: border-color 0.2s;
    outline: none;
    width: 100%;
  }

  textarea::placeholder { color: var(--text3); }
  textarea:focus { border-color: var(--accent); }

  /* FILTROS */
  .filters-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  select {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    color: var(--text2);
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    padding: 9px 12px;
    outline: none;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23555a68' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    transition: border-color 0.2s;
    width: 100%;
  }

  select:focus { border-color: var(--accent); }

  /* SEARCH BUTTON */
  .btn-search {
    width: 100%;
    padding: 14px;
    background: var(--accent);
    color: #0e0f11;
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.04em;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .btn-search:hover { background: var(--accent2); }
  .btn-search:active { transform: scale(0.99); }

  .btn-search:disabled {
    background: var(--surface2);
    color: var(--text3);
    cursor: not-allowed;
    transform: none;
  }

  .btn-search svg { width: 16px; height: 16px; }

  /* QUALITY INDICATOR */
  .quality-bar {
    display: none;
    flex-direction: column;
    gap: 6px;
  }

  .quality-bar.visible { display: flex; }

  .quality-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
  }

  .quality-label { color: var(--text3); font-family: 'DM Mono', monospace; }
  .quality-val { color: var(--text2); font-family: 'DM Mono', monospace; }
  .quality-val.good { color: var(--green); }
  .quality-val.warn { color: #ffaa4d; }
  .quality-val.bad { color: var(--red); }

  .quality-track {
    height: 3px;
    background: var(--surface2);
    border-radius: 2px;
    overflow: hidden;
  }

  .quality-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.4s ease;
  }

  /* RIGHT PANEL */
  .right-panel {
    display: flex;
    flex-direction: column;
    padding: 28px 28px;
    gap: 20px;
    overflow-y: auto;
  }

  .results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .results-count {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text3);
  }

  .results-count span { color: var(--accent); }

  .sort-row {
    display: flex;
    gap: 6px;
  }

  .sort-btn {
    padding: 5px 10px;
    border-radius: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text3);
    cursor: pointer;
    transition: all 0.15s;
  }

  .sort-btn.active {
    background: var(--surface2);
    border-color: var(--border2);
    color: var(--text2);
  }

  /* EMPTY STATE */
  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    color: var(--text3);
  }

  .empty-grid {
    display: grid;
    grid-template-columns: repeat(3, 64px);
    gap: 6px;
    opacity: 0.15;
  }

  .empty-cell {
    width: 64px; height: 64px;
    border: 1px solid var(--border2);
    border-radius: 8px;
    background: var(--surface);
  }

  .empty-cell:nth-child(2) { opacity: 0.6; }
  .empty-cell:nth-child(4) { opacity: 0.8; }
  .empty-cell:nth-child(6) { opacity: 0.4; }

  .empty-text {
    text-align: center;
  }

  .empty-text p { font-size: 14px; color: var(--text3); }
  .empty-text .sub { font-size: 12px; margin-top: 4px; }

  /* RESULTS GRID */
  .results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
  }

  /* RESULT CARD */
  .result-card {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s, transform 0.15s;
    animation: fadeIn 0.3s ease both;
  }

  .result-card:hover {
    border-color: var(--border2);
    transform: translateY(-2px);
  }

  .result-card.top-match {
    border-color: rgba(232, 255, 71, 0.4);
  }

  .result-card.selected {
    border-color: var(--accent);
    background: rgba(232, 255, 71, 0.04);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .card-img-wrap {
    aspect-ratio: 1;
    background: var(--surface2);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  .card-img-wrap img {
    width: 100%; height: 100%;
    object-fit: contain;
    padding: 12px;
  }

  .card-img-placeholder {
    width: 40px; height: 40px;
    opacity: 0.2;
  }

  .card-score-badge {
    position: absolute;
    top: 8px; right: 8px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    padding: 3px 7px;
    border-radius: 5px;
  }

  .score-high { background: rgba(77, 255, 145, 0.15); color: var(--green); }
  .score-mid  { background: rgba(255, 170, 77, 0.15); color: #ffaa4d; }
  .score-low  { background: rgba(138, 143, 158, 0.12); color: var(--text3); }

  .top-label {
    position: absolute;
    top: 8px; left: 8px;
    background: var(--accent);
    color: #0e0f11;
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    font-weight: 500;
    padding: 3px 7px;
    border-radius: 5px;
    letter-spacing: 0.06em;
  }

  .card-body {
    padding: 10px 12px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .card-id {
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
  }

  .card-ref {
    font-size: 11px;
    color: var(--text3);
    font-family: 'DM Mono', monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-tags {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-top: 4px;
  }

  .tag {
    font-size: 10px;
    font-family: 'DM Mono', monospace;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text3);
  }

  .tag.shape-round { border-color: #4d9fff44; color: var(--blue); background: rgba(77,159,255,0.08); }
  .tag.shape-square { border-color: #ff4d9f44; color: #ff4d9f; background: rgba(255,77,159,0.08); }
  .tag.shape-varios { border-color: #aa4dff44; color: #aa4dff; background: rgba(170,77,255,0.08); }
  .tag.fae { border-color: rgba(232,255,71,0.3); color: var(--accent); background: rgba(232,255,71,0.06); }

  /* DETAIL PANEL */
  .detail-panel {
    background: var(--surface);
    border: 1.5px solid var(--border2);
    border-radius: 14px;
    padding: 20px;
    display: none;
    flex-direction: column;
    gap: 16px;
    animation: fadeIn 0.25s ease;
  }

  .detail-panel.visible { display: flex; }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }

  .detail-id {
    font-family: 'DM Mono', monospace;
    font-size: 22px;
    font-weight: 500;
    color: var(--text);
    line-height: 1;
  }

  .detail-close {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    color: var(--text3);
    transition: all 0.15s;
  }

  .detail-close:hover { border-color: var(--border2); color: var(--text2); }

  .detail-img {
    width: 100%;
    aspect-ratio: 16/9;
    background: var(--surface2);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
  }

  .detail-img img {
    max-width: 100%; max-height: 100%;
    object-fit: contain;
    padding: 20px;
  }

  .detail-fields {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .detail-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .detail-field-label {
    font-size: 10px;
    font-family: 'DM Mono', monospace;
    color: var(--text3);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .detail-field-val {
    font-size: 13px;
    color: var(--text2);
    font-family: 'DM Mono', monospace;
  }

  .detail-field-val.highlight { color: var(--accent); }
  .detail-field-val.empty { color: var(--text3); font-style: italic; font-family: 'DM Sans', sans-serif; font-size: 12px; }

  .detail-actions {
    display: flex;
    gap: 8px;
  }

  .btn-confirm {
    flex: 1;
    padding: 11px;
    background: var(--accent);
    color: #0e0f11;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.04em;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-confirm:hover { background: var(--accent2); }

  .btn-reject {
    padding: 11px 14px;
    background: transparent;
    border: 1px solid var(--border2);
    border-radius: 8px;
    color: var(--text3);
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-reject:hover { border-color: var(--red); color: var(--red); }

  /* LOADING */
  .loading-overlay {
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    padding: 60px 0;
  }

  .loading-overlay.visible { display: flex; }

  .loader-ring {
    width: 40px; height: 40px;
    border: 2px solid var(--border2);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .loader-steps {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
  }

  .loader-step {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text3);
    opacity: 0;
    transition: opacity 0.3s, color 0.3s;
  }

  .loader-step.active { opacity: 1; color: var(--text2); }
  .loader-step.done { opacity: 0.5; color: var(--green); }

  /* TOAST */
  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 10px;
    padding: 12px 20px;
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--text2);
    transition: transform 0.3s ease;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .toast.show { transform: translateX(-50%) translateY(0); }
  .toast.success .toast-dot { background: var(--green); }
  .toast.info .toast-dot { background: var(--accent); }
  .toast-dot { width: 7px; height: 7px; border-radius: 50%; }

  /* DRAG & DROP */
  .drop-mask {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(14,15,17,0.8);
    z-index: 50;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }

  .drop-mask.visible { display: flex; }

  .drop-mask-inner {
    border: 2px dashed var(--accent);
    border-radius: 20px;
    padding: 60px 80px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .drop-mask-inner p {
    font-family: 'DM Mono', monospace;
    font-size: 16px;
    color: var(--accent);
    letter-spacing: 0.04em;
  }

  /* HIDDEN */
  #fileInput { display: none; }

  /* SCROLLBAR */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-mark">
      <svg viewBox="0 0 18 18" fill="none">
        <rect x="2" y="6" width="14" height="6" rx="1.5" stroke="#0e0f11" stroke-width="1.5"/>
        <circle cx="5" cy="9" r="1" fill="#0e0f11"/>
        <circle cx="9" cy="9" r="1" fill="#0e0f11"/>
        <circle cx="13" cy="9" r="1" fill="#0e0f11"/>
        <line x1="5" y1="6" x2="5" y2="4" stroke="#0e0f11" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="9" y1="6" x2="9" y2="4" stroke="#0e0f11" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="13" y1="6" x2="13" y2="4" stroke="#0e0f11" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="logo-text"><span>FAE</span> / identificador conectores</div>
  </div>
  <div class="header-right">
    <div class="status-dot"></div>
    <span>BD: 1049 conectores</span>
  </div>
</header>

<main>
  <!-- LEFT -->
  <div class="left-panel">
    <div class="panel-label">Entrada</div>

    <!-- Upload -->
    <div class="upload-zone" id="uploadZone">
      <img class="upload-preview" id="previewImg" src="" alt="preview">
      <div class="upload-badge" id="uploadBadge">imagen cargada</div>

      <div class="upload-placeholder">
        <div class="upload-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="3"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <path d="M21 15l-5-5L5 21"/>
          </svg>
        </div>
        <div class="upload-hint">
          <p>Arrastra una foto del conector<br>o haz clic para seleccionar</p>
          <p class="key">PNG · JPG · WEBP · máx. 10 MB</p>
        </div>
      </div>

      <div class="upload-actions">
        <button class="btn-small" onclick="clearImage(event)">Quitar</button>
        <button class="btn-small" onclick="triggerUpload(event)">Cambiar</button>
      </div>
    </div>
    <input type="file" id="fileInput" accept="image/*">

    <!-- Calidad imagen -->
    <div class="quality-bar" id="qualityBar">
      <div class="quality-row">
        <span class="quality-label">RESOLUCIÓN</span>
        <span class="quality-val good" id="qRes">—</span>
      </div>
      <div class="quality-track"><div class="quality-fill" id="qResBar" style="width:0;background:var(--green)"></div></div>
      <div class="quality-row">
        <span class="quality-label">NITIDEZ</span>
        <span class="quality-val good" id="qSharp">—</span>
      </div>
      <div class="quality-track"><div class="quality-fill" id="qSharpBar" style="width:0;background:var(--green)"></div></div>
    </div>

    <!-- Descripción -->
    <div class="field-group">
      <div class="field-label">
        Descripción
        <span class="optional-tag">opcional</span>
      </div>
      <textarea id="descInput" placeholder="ej: conector redondo 3 pines negro, plástico, cierre bayoneta…"></textarea>
    </div>

    <!-- Filtros -->
    <div class="field-group">
      <div class="field-label">
        Filtros
        <span class="optional-tag">opcional</span>
      </div>
      <div class="filters-row">
        <select id="filterForma">
          <option value="">Todas las formas</option>
          <option value="Redondo">Redondo</option>
          <option value="Cuadrado">Cuadrado</option>
          <option value="Varios">Varios</option>
          <option value="Borne/Terminal">Borne / Terminal</option>
        </select>
        <select id="filterPines">
          <option value="">Todos los pines</option>
          <option value="1">1 pin</option>
          <option value="2">2 pines</option>
          <option value="3">3 pines</option>
          <option value="4">4 pines</option>
          <option value="5">5+ pines</option>
        </select>
      </div>
    </div>

    <!-- Botón buscar -->
    <button class="btn-search" id="searchBtn" onclick="runSearch()" disabled>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <path d="M21 21l-4.35-4.35"/>
      </svg>
      Identificar conector
    </button>
  </div>

  <!-- RIGHT -->
  <div class="right-panel" id="rightPanel">

    <!-- Empty state -->
    <div class="empty-state" id="emptyState">
      <div class="empty-grid">
        <div class="empty-cell"></div>
        <div class="empty-cell"></div>
        <div class="empty-cell"></div>
        <div class="empty-cell"></div>
        <div class="empty-cell"></div>
        <div class="empty-cell"></div>
      </div>
      <div class="empty-text">
        <p>Carga una foto para comenzar</p>
        <p class="sub">El sistema buscará los conectores más similares</p>
      </div>
    </div>

    <!-- Loading -->
    <div class="loading-overlay" id="loadingOverlay">
      <div class="loader-ring"></div>
      <div class="loader-steps">
        <div class="loader-step" id="step1">Procesando imagen…</div>
        <div class="loader-step" id="step2">Generando embedding visual…</div>
        <div class="loader-step" id="step3">Buscando similares en BD…</div>
        <div class="loader-step" id="step4">Ordenando candidatos…</div>
      </div>
    </div>

    <!-- Results -->
    <div id="resultsSection" style="display:none; flex-direction:column; gap:16px;">
      <div class="results-header">
        <div class="results-count">
          <span id="resultsNum">0</span> candidatos encontrados
        </div>
        <div class="sort-row">
          <button class="sort-btn active" onclick="setSortMode('sim', this)">Similitud</button>
          <button class="sort-btn" onclick="setSortMode('id', this)">ID</button>
        </div>
      </div>

      <!-- Detail panel -->
      <div class="detail-panel" id="detailPanel">
        <div class="detail-header">
          <div>
            <div style="font-size:10px;font-family:'DM Mono',monospace;color:var(--text3);letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">Seleccionado</div>
            <div class="detail-id" id="detailId">—</div>
          </div>
          <button class="detail-close" onclick="closeDetail()">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="detail-img">
          <img id="detailImg" src="" alt="">
        </div>
        <div class="detail-fields">
          <div class="detail-field">
            <div class="detail-field-label">Referencia FAE</div>
            <div class="detail-field-val highlight" id="detailRef">—</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Similitud</div>
            <div class="detail-field-val" id="detailScore">—</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Forma</div>
            <div class="detail-field-val" id="detailForma">—</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Terminales</div>
            <div class="detail-field-val" id="detailPines">—</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Es de FAE</div>
            <div class="detail-field-val" id="detailFae">—</div>
          </div>
          <div class="detail-field">
            <div class="detail-field-label">Contraconector</div>
            <div class="detail-field-val empty" id="detailContra">sin asignar</div>
          </div>
        </div>
        <div class="detail-actions">
          <button class="btn-confirm" onclick="confirmMatch()">✓ Confirmar identificación</button>
          <button class="btn-reject" onclick="rejectMatch()">Descartar</button>
        </div>
      </div>

      <!-- Cards grid -->
      <div class="results-grid" id="resultsGrid"></div>
    </div>

  </div>
</main>

<!-- Drop mask -->
<div class="drop-mask" id="dropMask">
  <div class="drop-mask-inner">
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <path d="M20 8v16M12 16l8-8 8 8" stroke="#e8ff47" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M8 28h24" stroke="#e8ff47" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
    </svg>
    <p>suelta la imagen aquí</p>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast">
  <div class="toast-dot"></div>
  <span id="toastMsg"></span>
</div>

<script>
// ── MOCK DATA ─────────────────────────────────────────────────────────
// Conectores de muestra (en producción vendrían del backend)
const MOCK_DB = [
  { id: '932',  ref: '311175', forma: 'Cuadrado', pines: 4, fae: false, score: 0.94 },
  { id: '830',  ref: '311183', forma: 'Cuadrado', pines: 2, fae: false, score: 0.91 },
  { id: '936',  ref: '311176', forma: 'Redondo',  pines: 4, fae: false, score: 0.87 },
  { id: '935',  ref: '311156', forma: 'Cuadrado', pines: 4, fae: false, score: 0.83 },
  { id: '947',  ref: '311174', forma: 'Varios',   pines: 2, fae: false, score: 0.79 },
  { id: '943',  ref: '311185', forma: 'Varios',   pines: 3, fae: false, score: 0.74 },
  { id: '817',  ref: '',       forma: 'Cuadrado', pines: 2, fae: true,  score: 0.68 },
  { id: '950',  ref: '311161', forma: 'Varios',   pines: 3, fae: false, score: 0.61 },
];

// Colores SVG placeholder por forma
function placeholderSVG(forma) {
  const colors = { Redondo: '#4d9fff', Cuadrado: '#ff4d9f', Varios: '#aa4dff', '': '#555a68' };
  const c = colors[forma] || '#555a68';
  if (forma === 'Redondo') {
    return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><circle cx='40' cy='40' r='28' fill='none' stroke='${c}' stroke-width='2' opacity='0.5'/><circle cx='30' cy='40' r='4' fill='${c}' opacity='0.7'/><circle cx='40' cy='40' r='4' fill='${c}' opacity='0.7'/><circle cx='50' cy='40' r='4' fill='${c}' opacity='0.7'/></svg>`)}`;
  }
  if (forma === 'Cuadrado') {
    return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect x='16' y='24' width='48' height='32' rx='4' fill='none' stroke='${c}' stroke-width='2' opacity='0.5'/><rect x='26' y='34' width='8' height='12' rx='2' fill='${c}' opacity='0.7'/><rect x='46' y='34' width='8' height='12' rx='2' fill='${c}' opacity='0.7'/></svg>`)}`;
  }
  return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect x='20' y='28' width='40' height='24' rx='3' fill='none' stroke='${c}' stroke-width='2' opacity='0.4'/><circle cx='30' cy='40' r='3' fill='${c}' opacity='0.6'/><circle cx='40' cy='40' r='3' fill='${c}' opacity='0.6'/><circle cx='50' cy='40' r='3' fill='${c}' opacity='0.6'/></svg>`)}`;
}

// ── STATE ─────────────────────────────────────────────────────────────
let hasImage = false;
let currentResults = [];
let selectedCard = null;
let sortMode = 'sim';

// ── UPLOAD ────────────────────────────────────────────────────────────
const uploadZone = document.getElementById('uploadZone');
const fileInput  = document.getElementById('fileInput');
const previewImg = document.getElementById('previewImg');
const searchBtn  = document.getElementById('searchBtn');

uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => { if (e.target.files[0]) loadImage(e.target.files[0]); });

uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) loadImage(e.dataTransfer.files[0]);
});

// Global drag
document.addEventListener('dragover', e => { e.preventDefault(); document.getElementById('dropMask').classList.add('visible'); });
document.addEventListener('dragleave', e => { if (!e.relatedTarget) document.getElementById('dropMask').classList.remove('visible'); });
document.addEventListener('drop', e => {
  e.preventDefault();
  document.getElementById('dropMask').classList.remove('visible');
  if (e.dataTransfer.files[0]) loadImage(e.dataTransfer.files[0]);
});

function triggerUpload(e) { e.stopPropagation(); fileInput.click(); }

function clearImage(e) {
  e.stopPropagation();
  hasImage = false;
  previewImg.src = '';
  uploadZone.classList.remove('has-image');
  searchBtn.disabled = true;
  document.getElementById('qualityBar').classList.remove('visible');
  fileInput.value = '';
  resetResults();
}

function loadImage(file) {
  if (!file.type.startsWith('image/')) { showToast('Solo se aceptan imágenes', 'info'); return; }
  const reader = new FileReader();
  reader.onload = e => {
    previewImg.src = e.target.result;
    uploadZone.classList.add('has-image');
    hasImage = true;
    searchBtn.disabled = false;
    analyzeQuality(e.target.result);
    resetResults();
  };
  reader.readAsDataURL(file);
}

function analyzeQuality(dataUrl) {
  // Mock quality analysis
  const img = new Image();
  img.onload = () => {
    const w = img.naturalWidth, h = img.naturalHeight;
    const qBar = document.getElementById('qualityBar');
    qBar.classList.add('visible');
    
    const resPct = Math.min(100, (Math.min(w, h) / 640) * 100);
    const sharpPct = 60 + Math.random() * 35; // mock
    
    const resEl = document.getElementById('qRes');
    const resBar = document.getElementById('qResBar');
    resEl.textContent = `${w}×${h}`;
    resEl.className = 'quality-val ' + (resPct > 60 ? 'good' : resPct > 30 ? 'warn' : 'bad');
    resBar.style.width = resPct + '%';
    resBar.style.background = resPct > 60 ? 'var(--green)' : resPct > 30 ? '#ffaa4d' : 'var(--red)';
    
    const sharpEl = document.getElementById('qSharp');
    const sharpBar = document.getElementById('qSharpBar');
    sharpEl.textContent = sharpPct > 70 ? 'buena' : sharpPct > 40 ? 'aceptable' : 'baja';
    sharpEl.className = 'quality-val ' + (sharpPct > 70 ? 'good' : sharpPct > 40 ? 'warn' : 'bad');
    sharpBar.style.width = sharpPct + '%';
    sharpBar.style.background = sharpPct > 70 ? 'var(--green)' : sharpPct > 40 ? '#ffaa4d' : 'var(--red)';
  };
  img.src = dataUrl;
}

// ── SEARCH ────────────────────────────────────────────────────────────
function runSearch() {
  if (!hasImage) return;
  
  resetResults();
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('loadingOverlay').classList.add('visible');
  document.getElementById('resultsSection').style.display = 'none';
  searchBtn.disabled = true;
  
  // Simulate step-by-step loading
  const steps = ['step1','step2','step3','step4'];
  const delays = [0, 500, 1100, 1700];
  
  steps.forEach((s, i) => {
    setTimeout(() => {
      // Mark previous as done
      if (i > 0) document.getElementById(steps[i-1]).classList.remove('active');
      if (i > 0) document.getElementById(steps[i-1]).classList.add('done');
      document.getElementById(s).classList.add('active');
    }, delays[i]);
  });
  
  setTimeout(() => {
    document.getElementById(steps[steps.length-1]).classList.add('done');
    document.getElementById(steps[steps.length-1]).classList.remove('active');
    
    setTimeout(() => {
      document.getElementById('loadingOverlay').classList.remove('visible');
      
      // Reset step classes
      steps.forEach(s => {
        document.getElementById(s).classList.remove('active','done');
      });
      
      // Apply filters
      const forma = document.getElementById('filterForma').value;
      const pines = document.getElementById('filterPines').value;
      
      let filtered = [...MOCK_DB];
      if (forma) filtered = filtered.filter(c => c.forma === forma);
      if (pines) {
        const p = parseInt(pines);
        if (p === 5) filtered = filtered.filter(c => c.pines >= 5);
        else filtered = filtered.filter(c => c.pines === p);
      }
      
      // Add slight score variation for demo
      currentResults = filtered.map(c => ({
        ...c,
        score: Math.min(0.99, c.score + (Math.random() - 0.5) * 0.05)
      }));
      
      renderResults();
      searchBtn.disabled = false;
    }, 200);
  }, 2300);
}

function renderResults() {
  const section = document.getElementById('resultsSection');
  section.style.display = 'flex';
  
  const sorted = sortResults(currentResults);
  document.getElementById('resultsNum').textContent = sorted.length;
  
  const grid = document.getElementById('resultsGrid');
  grid.innerHTML = '';
  
  sorted.forEach((c, idx) => {
    const scoreClass = c.score > 0.85 ? 'score-high' : c.score > 0.65 ? 'score-mid' : 'score-low';
    const shapeTag = c.forma ? `<span class="tag shape-${c.forma.toLowerCase().replace('/','-')}">${c.forma}</span>` : '';
    const pinesTag = c.pines ? `<span class="tag">${c.pines}p</span>` : '';
    const faeTag = c.fae ? `<span class="tag fae">FAE</span>` : '';
    const isTop = idx === 0 && sortMode === 'sim';
    
    const card = document.createElement('div');
    card.className = 'result-card' + (isTop ? ' top-match' : '');
    card.style.animationDelay = (idx * 0.04) + 's';
    card.dataset.id = c.id;
    card.innerHTML = `
      <div class="card-img-wrap">
        <img src="${placeholderSVG(c.forma)}" alt="Conector ${c.id}">
        ${isTop ? '<span class="top-label">mejor</span>' : ''}
        <span class="card-score-badge ${scoreClass}">${Math.round(c.score * 100)}%</span>
      </div>
      <div class="card-body">
        <div class="card-id">#${c.id}</div>
        <div class="card-ref">${c.ref || 'sin referencia'}</div>
        <div class="card-tags">${shapeTag}${pinesTag}${faeTag}</div>
      </div>
    `;
    card.addEventListener('click', () => openDetail(c, card));
    grid.appendChild(card);
  });
}

function sortResults(results) {
  if (sortMode === 'sim') return [...results].sort((a,b) => b.score - a.score);
  return [...results].sort((a,b) => parseInt(a.id) - parseInt(b.id));
}

function setSortMode(mode, btn) {
  sortMode = mode;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (currentResults.length) renderResults();
}

// ── DETAIL ────────────────────────────────────────────────────────────
function openDetail(c, cardEl) {
  if (selectedCard) selectedCard.classList.remove('selected');
  selectedCard = cardEl;
  cardEl.classList.add('selected');
  
  document.getElementById('detailId').textContent = '#' + c.id;
  document.getElementById('detailImg').src = placeholderSVG(c.forma);
  
  const refEl = document.getElementById('detailRef');
  refEl.textContent = c.ref || '—';
  refEl.className = 'detail-field-val ' + (c.ref ? 'highlight' : 'empty');
  if (!c.ref) refEl.textContent = 'sin referencia FAE';
  
  document.getElementById('detailScore').textContent = Math.round(c.score * 100) + '% similitud';
  document.getElementById('detailForma').textContent = c.forma || '—';
  document.getElementById('detailPines').textContent = c.pines ? c.pines + ' terminales' : '—';
  
  const faeEl = document.getElementById('detailFae');
  faeEl.textContent = c.fae ? 'Sí' : 'No';
  faeEl.className = 'detail-field-val ' + (c.fae ? 'highlight' : '');
  
  document.getElementById('detailPanel').classList.add('visible');
  document.getElementById('detailPanel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeDetail() {
  document.getElementById('detailPanel').classList.remove('visible');
  if (selectedCard) { selectedCard.classList.remove('selected'); selectedCard = null; }
}

function confirmMatch() {
  const id = document.getElementById('detailId').textContent;
  showToast(`Conector ${id} confirmado`, 'success');
  closeDetail();
}

function rejectMatch() {
  if (selectedCard) {
    selectedCard.style.opacity = '0.3';
    selectedCard.style.pointerEvents = 'none';
    selectedCard = null;
    document.getElementById('detailPanel').classList.remove('visible');
  }
}

// ── UTILS ─────────────────────────────────────────────────────────────
function resetResults() {
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('emptyState').style.display = '';
  document.getElementById('detailPanel').classList.remove('visible');
  document.getElementById('resultsGrid').innerHTML = '';
  currentResults = [];
  selectedCard = null;
}

let toastTimer;
function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  toast.className = 'toast ' + type;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}
</script>
</body>
</html>