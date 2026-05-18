/* ── Estado ────────────────────────────────────────────────────────────── */
const state = {
  loja:         null,
  categoria:    null,
  lojasData:    [],   // [{id, nome, descricao, categoria_default, categorias: [{id, nome}]}]
  modo:         null,
  arquivo:      null,
  jobId:        null,
  pollingTimer: null,
};

/* ── Helpers DOM ───────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const lojasGrid      = $('lojas-grid');
const categoriasRow  = $('categorias-row');
const categoriasGrid = $('categorias-grid');
const dropzone       = $('dropzone');
const fileInput      = $('file-input');
const fileSelected   = $('file-selected');
const fileName       = $('file-name');
const btnProcessar      = $('btn-processar');
const btnProcessarLabel = $('btn-processar-label');

const formSection     = $('form-section');
const progressSection = $('progress-section');
const resultSection   = $('result-section');
const errorSection    = $('error-section');

const progressLabel   = $('progress-label');
const progressPct     = $('progress-pct');
const progressBarFill = $('progress-bar-fill');
const progressBar     = progressSection?.querySelector('[role=progressbar]');

const resultSubtitle    = $('result-subtitle');
const btnDownloadShopee     = $('btn-download-shopee');
const btnDownloadErp        = $('btn-download-erp');
const btnDownloadKakashi    = $('btn-download-kakashi');
const btnDownloadRejeitados = $('btn-download-rejeitados');
const downloadRejeitadosHint= $('download-rejeitados-hint');

// Revisão de capas (entre fase 1 e fase 2 — descarte + ajuste de crop)
const reviewSection = $('review-section');
const reviewGrid    = $('review-grid');
const reviewStatus  = $('review-status');
const btnConfirmar  = $('btn-confirmar');
const descartadosSet = new Set();  // SKUs base marcados pra descartar

// Modal de ajuste de crop (Cropper.js)
const cropperModal       = $('cropper-modal');
const cropperModalTitle  = $('cropper-modal-title');
const cropperModalClose  = $('cropper-modal-close');
const cropperImg         = $('cropper-img');
const cropperCancel      = $('cropper-cancel');
const cropperSave        = $('cropper-save');
const cropperState       = { instance: null, sku_base: null, image_url: null, naturalSize: null };
const avisosBox         = $('avisos-box');
const avisosLista       = $('avisos-lista');
const btnNovaPlanilha   = $('btn-nova-planilha');

const errorMsg           = $('error-msg');
const btnTentarNovamente = $('btn-tentar-novamente');

// Card secundário "Gerar Planilha de Desconto" (fluxo 2-etapas)
const descontoFileInput  = $('desconto-file-input');
const descontoFileBtn    = $('desconto-file-btn');
const descontoFilename   = $('desconto-filename');
const btnDesconto        = $('btn-desconto');
const descontoStatus     = $('desconto-status');
const descontoState      = { arquivo: null };

// Banco de SKUs em uso
const skusEntrySection = $('skus-entry-section');
const btnAbrirSkus     = $('btn-abrir-skus');
const skusSection      = $('skus-section');
const btnFecharSkus    = $('btn-fechar-skus');
const skusBusca        = $('skus-busca');
const skusLojasFiltro  = $('skus-lojas-filtro');
const skusSort         = $('skus-sort');
const skusTbody        = $('skus-tbody');
const skusStatus       = $('skus-status');
const skusState        = { todos: [], filtroLoja: '', filtroBusca: '', sort: 'criado_desc' };

// Banco Kakashi
const kakashiEntrySection = $('kakashi-entry-section');
const btnAbrirKakashi     = $('btn-abrir-kakashi');
const kakashiSection      = $('kakashi-section');
const btnFecharKakashi    = $('btn-fechar-kakashi');
const kakashiBusca        = $('kakashi-busca');
const kakashiLojasFiltro  = $('kakashi-lojas-filtro');
const kakashiStatusFiltro = $('kakashi-status-filtro');
const kakashiSort         = $('kakashi-sort');
const kakashiTbody        = $('kakashi-tbody');
const kakashiStatusInfo   = $('kakashi-status-info');
const kakashiCheckAll     = $('kakashi-check-all');
const kakashiSelecaoInfo  = $('kakashi-selecao-info');
const btnBaixarKakashi    = $('btn-baixar-kakashi');
const kakashiState = {
  todos: [],
  filtroLoja: '',
  filtroBusca: '',
  filtroStatus: 'pendente',
  sort: 'criado_desc',
  selecionados: new Set(),
};

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  inicializarTema();
  carregarLojas();
  configurarModos();
  configurarDropzone();
  configurarBotoes();
  configurarDesconto();
  configurarSkusViewer();
  configurarKakashiViewer();
});

/* ── Lojas ──────────────────────────────────────────────────────────────── */
async function carregarLojas() {
  const FALLBACK = [
    { id: 'PPJ',        nome: 'PPJ',        descricao: 'Quadros religiosos e minimalistas',
      categoria_default: 'padrao', categorias: [{ id: 'padrao', nome: 'Padrão' }] },
    { id: 'iPaper',     nome: 'iPaper',     descricao: 'Arte, Bauhaus e design moderno',
      categoria_default: 'padrao', categorias: [{ id: 'padrao', nome: 'Padrão' }] },
    { id: 'AllQuadros', nome: 'AllQuadros', descricao: 'Moderno, minimalista, boho',
      categoria_default: 'padrao', categorias: [
        { id: 'padrao',   nome: 'Padrão' },
        { id: 'infantil', nome: 'Infantil' },
      ]},
  ];
  try {
    const res  = await fetch('/api/lojas');
    const data = await res.json();
    renderizarLojas(data.lojas && data.lojas.length ? data.lojas : FALLBACK);
  } catch {
    renderizarLojas(FALLBACK);
  }
}

function renderizarLojas(lojas) {
  state.lojasData = lojas;
  lojasGrid.innerHTML = '';
  lojas.forEach(loja => {
    const card = document.createElement('div');
    card.className = 'loja-card';
    card.dataset.id = loja.id;
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-pressed', 'false');
    card.innerHTML = `
      <span class="loja-nome">${loja.nome}</span>
      <span class="loja-desc">${loja.descricao}</span>
    `;
    card.addEventListener('click', () => selecionarLoja(loja.id));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selecionarLoja(loja.id); }
    });
    lojasGrid.appendChild(card);
  });
}

function selecionarLoja(id) {
  state.loja = id;
  lojasGrid.querySelectorAll('.loja-card').forEach(c => {
    const sel = c.dataset.id === id;
    c.classList.toggle('selecionada', sel);
    c.setAttribute('aria-pressed', String(sel));
  });

  // Renderizar sub-selecao de categoria se a loja tiver >1 categoria.
  const loja = state.lojasData.find(l => l.id === id);
  const cats = (loja && loja.categorias) || [];
  if (cats.length > 1) {
    state.categoria = loja.categoria_default || cats[0].id;
    renderizarCategorias(cats);
    if (categoriasRow) categoriasRow.style.display = '';
  } else {
    state.categoria = cats[0] ? cats[0].id : (loja && loja.categoria_default) || 'padrao';
    if (categoriasGrid) categoriasGrid.innerHTML = '';
    if (categoriasRow) categoriasRow.style.display = 'none';
  }
  atualizarBotao();
}

function renderizarCategorias(cats) {
  if (!categoriasGrid) return;
  categoriasGrid.innerHTML = '';
  cats.forEach(cat => {
    const btn = document.createElement('div');
    btn.className = 'categoria-card';
    btn.dataset.id = cat.id;
    btn.setAttribute('role', 'button');
    btn.setAttribute('tabindex', '0');
    btn.setAttribute('aria-pressed', String(cat.id === state.categoria));
    btn.classList.toggle('selecionada', cat.id === state.categoria);
    btn.textContent = cat.nome;
    btn.addEventListener('click', () => selecionarCategoria(cat.id));
    btn.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selecionarCategoria(cat.id); }
    });
    categoriasGrid.appendChild(btn);
  });
}

function selecionarCategoria(id) {
  state.categoria = id;
  if (categoriasGrid) {
    categoriasGrid.querySelectorAll('.categoria-card').forEach(c => {
      const sel = c.dataset.id === id;
      c.classList.toggle('selecionada', sel);
      c.setAttribute('aria-pressed', String(sel));
    });
  }
}

/* ── Modos ──────────────────────────────────────────────────────────────── */
function configurarModos() {
  document.querySelectorAll('input[name="modo"]').forEach(radio => {
    radio.addEventListener('change', () => {
      state.modo = radio.value;
      // Atualizar visual dos cards
      document.querySelectorAll('.modo-card').forEach(card => {
        const inp = card.querySelector('input[name="modo"]');
        card.classList.toggle('selecionado', inp && inp.checked);
      });
    });
  });
}

/* ── Download do modelo ─────────────────────────────────────────────────── */
function baixarModelo(tipo) {
  const a = document.createElement('a');
  a.href = `/api/modelo/${tipo}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/* ── Dropzone ───────────────────────────────────────────────────────────── */
function configurarDropzone() {
  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) definirArquivo(fileInput.files[0]);
  });

  ['dragenter', 'dragover'].forEach(evt => {
    dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  });

  ['dragleave', 'dragend'].forEach(evt => {
    dropzone.addEventListener(evt, () => dropzone.classList.remove('drag-over'));
  });

  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) definirArquivo(e.dataTransfer.files[0]);
  });
}

function definirArquivo(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['xlsx', 'xls', 'csv'].includes(ext)) {
    mostrarErro(`Formato inválido ".${ext}". Use .xlsx, .xls ou .csv`);
    return;
  }
  state.arquivo = file;
  fileName.textContent = file.name;
  fileSelected.style.display = 'flex';
  atualizarBotao();
}

/* ── Botões ─────────────────────────────────────────────────────────────── */
function configurarBotoes() {
  btnProcessar.addEventListener('click', iniciarProcessamento);
  btnNovaPlanilha?.addEventListener('click', resetar);
  btnTentarNovamente?.addEventListener('click', resetar);
  btnDownloadShopee?.addEventListener('click', () => baixarArquivo('shopee'));
  btnDownloadErp?.addEventListener('click', () => baixarArquivo('erp'));
  btnDownloadKakashi?.addEventListener('click', () => baixarArquivo('kakashi'));
  btnDownloadRejeitados?.addEventListener('click', () => baixarArquivo('rejeitados'));
  // Modal de crop (<dialog> nativo)
  cropperModalClose?.addEventListener('click', fecharCropper);
  cropperCancel?.addEventListener('click', fecharCropper);
  cropperSave?.addEventListener('click', salvarCropper);
  // Click fora da janela (no ::backdrop) fecha o dialog. Detecta via bounding rect
  // porque clicks no backdrop tem o <dialog> como event.target (estranho mas e o
  // comportamento padrao do <dialog>).
  cropperModal?.addEventListener('click', (e) => {
    if (e.target !== cropperModal) return;  // click foi num filho, ignora
    const rect = cropperModal.getBoundingClientRect();
    const dentro = e.clientX >= rect.left && e.clientX <= rect.right &&
                   e.clientY >= rect.top  && e.clientY <= rect.bottom;
    if (!dentro) fecharCropper();
  });
  // ESC tambem fecha (handler do <dialog> dispara `cancel` event)
  cropperModal?.addEventListener('cancel', (e) => {
    e.preventDefault();
    fecharCropper();
  });
}

function atualizarBotao() {
  btnProcessar.disabled = !(state.loja && state.modo && state.arquivo);
  if (btnProcessarLabel) {
    btnProcessarLabel.textContent = state.loja
      ? `Processar como ${state.loja}`
      : 'Processar Planilha';
  }
}

/* ── Processamento ─────────────────────────────────────────────────────── */
async function iniciarProcessamento() {
  if (!state.loja || !state.arquivo) return;

  const formData = new FormData();
  formData.append('arquivo', state.arquivo);
  formData.append('loja', state.loja);
  formData.append('modo', state.modo);
  if (state.categoria) formData.append('categoria', state.categoria);

  mostrarSecao('progress');
  atualizarProgresso('Enviando arquivo...', 2);

  try {
    const res  = await fetch('/api/processar', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) {
      mostrarErro(data.detail || 'Erro ao iniciar processamento.');
      return;
    }

    state.jobId = data.job_id;
    iniciarPolling();
  } catch {
    mostrarErro('Não foi possível conectar ao servidor. Verifique se ele está rodando.');
  }
}

function iniciarPolling() {
  state.pollingTimer = setInterval(consultarStatus, 2000);
}

function pararPolling() {
  if (state.pollingTimer) { clearInterval(state.pollingTimer); state.pollingTimer = null; }
}

async function consultarStatus() {
  if (!state.jobId) return;
  try {
    const res  = await fetch(`/api/status/${state.jobId}`);
    if (!res.ok) { pararPolling(); mostrarErro('Job não encontrado. Tente novamente.'); return; }

    const data = await res.json();
    atualizarProgresso(data.mensagem || '', data.percent || 0);

    if (data.status === 'aguardando_confirmacao') {
      pararPolling();
      mostrarRevisao();
    } else if (data.status === 'concluido') {
      pararPolling();
      mostrarResultado(data);
    } else if (data.status === 'erro') {
      pararPolling();
      mostrarErro(data.erro || data.mensagem || 'Erro desconhecido.', data.avisos);
    }
  } catch { /* retry na próxima iteração */ }
}

/* ── UI ─────────────────────────────────────────────────────────────────── */
function mostrarSecao(secao) {
  // formSection é um wrapper com display: contents (ver HTML) — preserva o grid
  formSection.style.display     = secao === 'form'     ? 'contents' : 'none';
  progressSection.style.display = secao === 'progress' ? 'flex'     : 'none';
  if (reviewSection) reviewSection.style.display = secao === 'review' ? 'flex' : 'none';
  resultSection.style.display   = secao === 'result'   ? 'flex'     : 'none';
  errorSection.style.display    = secao === 'error'    ? 'block'    : 'none';
  btnProcessar.style.display    = secao === 'form'     ? 'flex'     : 'none';
}

async function mostrarRevisao() {
  mostrarSecao('review');
  if (state.jobId) await carregarRevisaoCapas(state.jobId);
}

function atualizarProgresso(mensagem, pct) {
  progressLabel.textContent     = mensagem;
  progressPct.textContent       = `${pct}%`;
  progressBarFill.style.width   = `${pct}%`;
  if (progressBar) progressBar.setAttribute('aria-valuenow', String(pct));
}

function mostrarResultado(data) {
  const n = data.produtos || 0;
  const rej = data.rejeitados || 0;
  if (rej > 0) {
    resultSubtitle.textContent =
      `${n} produto${n !== 1 ? 's' : ''} OK + ${rej} rejeitado${rej !== 1 ? 's' : ''} (baixe a planilha "Rejeitados" pra revisar).`;
  } else {
    resultSubtitle.textContent = `${n} produto${n !== 1 ? 's' : ''} processado${n !== 1 ? 's' : ''} com sucesso.`;
  }

  // Botao "Planilha de Rejeitados" so aparece se houver
  if (btnDownloadRejeitados) {
    if (data.tem_rejeitados && rej > 0) {
      btnDownloadRejeitados.style.display = '';
      if (downloadRejeitadosHint) {
        downloadRejeitadosHint.textContent =
          `${rej} produto${rej !== 1 ? 's' : ''} com falha — revisar e retentar`;
      }
    } else {
      btnDownloadRejeitados.style.display = 'none';
    }
  }

  if (data.avisos?.length) {
    avisosLista.innerHTML = '';
    data.avisos.forEach(av => {
      const li = document.createElement('li');
      li.textContent = av;
      avisosLista.appendChild(li);
    });
    avisosBox.style.display = '';
  } else {
    avisosBox.style.display = 'none';
  }

  mostrarSecao('result');
}

/* ── Revisão de capas (entre fase 1 e fase 2 — descarte + ajuste crop) ──── */
async function carregarRevisaoCapas(jobId) {
  if (!reviewSection || !reviewGrid) return;
  try {
    const res = await fetch(`/api/produtos/${jobId}`);
    if (!res.ok) {
      mostrarErro('Falha ao carregar produtos pra revisão.');
      return;
    }
    const data = await res.json();
    if (!data.produtos?.length) {
      mostrarErro('Nenhum produto disponível pra revisão.');
      return;
    }
    renderizarRevisao(data.produtos);
  } catch (err) {
    mostrarErro(`Erro de rede: ${err.message || err}`);
  }
}

function renderizarRevisao(produtos) {
  reviewGrid.innerHTML = '';
  descartadosSet.clear();

  produtos.forEach(p => {
    const item = document.createElement('div');
    item.className = 'review-item';
    item.dataset.sku = p.sku_base;
    item.innerHTML = `
      <img class="review-thumb" src="${p.imagem_capa}"
           alt="Capa ${p.display}" loading="lazy"
           onerror="this.style.background='#fee'; this.alt='Capa não carregou'">
      <div class="review-info">
        <span class="review-sku">${p.sku_completo}</span>
        <span class="review-display">${p.display}</span>
      </div>
      <div class="review-actions-item">
        <button type="button" class="btn-secondary btn-recrop"
                ${p.imagem_capa_original ? '' : 'disabled title="Sem URL original"'}>
          Ajustar crop
        </button>
        <label class="review-descartar">
          <input type="checkbox" aria-label="Descartar ${p.sku_completo}">
          Descartar
        </label>
      </div>
    `;
    const chk = item.querySelector('input[type="checkbox"]');
    chk.addEventListener('change', () => {
      if (chk.checked) {
        descartadosSet.add(p.sku_base);
        item.classList.add('descartar');
      } else {
        descartadosSet.delete(p.sku_base);
        item.classList.remove('descartar');
      }
      atualizarStatusRevisao();
    });
    const btnRecrop = item.querySelector('.btn-recrop');
    if (btnRecrop && p.imagem_capa_original) {
      btnRecrop.addEventListener('click', () => abrirCropper(p));
    }
    reviewGrid.appendChild(item);
  });
  atualizarStatusRevisao();

  if (btnConfirmar && !btnConfirmar.dataset.bound) {
    btnConfirmar.addEventListener('click', confirmarEgerar);
    btnConfirmar.dataset.bound = '1';
  }
}

function atualizarStatusRevisao() {
  const n = descartadosSet.size;
  if (reviewStatus) {
    reviewStatus.textContent = n === 0
      ? 'Nenhum descarte marcado'
      : `${n} produto${n !== 1 ? 's' : ''} marcado${n !== 1 ? 's' : ''} pra descarte`;
  }
}

async function confirmarEgerar() {
  if (!state.jobId) return;
  const skus = [...descartadosSet];
  if (skus.length > 0 && !confirm(`Confirmar ${skus.length} descarte(s) e gerar planilhas?`)) return;

  btnConfirmar.disabled = true;
  const labelOriginal = btnConfirmar.textContent;
  btnConfirmar.textContent = 'Confirmando...';

  try {
    const res = await fetch('/api/confirmar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: state.jobId, descartes: skus }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Erro: ${data.detail || 'desconhecido'}`);
      btnConfirmar.disabled = false;
      btnConfirmar.textContent = labelOriginal;
      return;
    }
    // Sucesso — fase 2 iniciada, volta pra tela de progresso e re-polling
    mostrarSecao('progress');
    atualizarProgresso('Gerando planilhas...', 90);
    iniciarPolling();
  } catch (err) {
    alert(`Erro de rede: ${err.message || err}`);
    btnConfirmar.disabled = false;
    btnConfirmar.textContent = labelOriginal;
  }
}

/* ── Cropper modal (ajustar enquadramento da capa) ───────────────────────── */
function abrirCropper(produto) {
  if (!cropperModal || !cropperImg) return;
  if (!produto.imagem_capa_original) {
    alert('Sem URL original disponível pra esse produto.');
    return;
  }
  if (typeof Cropper === 'undefined') {
    alert('Cropper.js não carregou. Recarregue a página.');
    return;
  }

  cropperState.sku_base  = produto.sku_base;
  cropperState.image_url = produto.imagem_capa_original;
  cropperState.naturalSize = null;
  if (cropperModalTitle) cropperModalTitle.textContent = `Ajustar crop — ${produto.sku_completo}`;

  // Limpa instancia anterior
  if (cropperState.instance) {
    cropperState.instance.destroy();
    cropperState.instance = null;
  }

  cropperImg.onload = () => {
    cropperState.naturalSize = { w: cropperImg.naturalWidth, h: cropperImg.naturalHeight };
    cropperState.instance = new Cropper(cropperImg, {
      aspectRatio: 1,
      viewMode: 1,
      autoCropArea: 0.9,
      background: false,
      movable: true,
      zoomable: true,
      responsive: true,
    });
  };
  cropperImg.onerror = () => {
    alert('Não foi possível carregar a imagem original (CORS ou link quebrado).');
    fecharCropper();
  };
  // Bust cache pra evitar imagem stale + força recarga
  cropperImg.src = produto.imagem_capa_original;
  // <dialog>.showModal() renderiza no top layer + bloqueia interacao com a pagina
  if (typeof cropperModal.showModal === 'function') {
    if (!cropperModal.open) cropperModal.showModal();
  } else {
    // Fallback (browser < 2022): display flex como antes
    cropperModal.style.display = 'flex';
  }
}

function fecharCropper() {
  if (cropperState.instance) {
    cropperState.instance.destroy();
    cropperState.instance = null;
  }
  cropperState.sku_base = null;
  cropperState.image_url = null;
  cropperState.naturalSize = null;
  if (cropperModal) {
    if (typeof cropperModal.close === 'function' && cropperModal.open) {
      cropperModal.close();
    } else {
      cropperModal.style.display = 'none';
    }
  }
}

async function salvarCropper() {
  if (!cropperState.instance || !cropperState.sku_base) return;

  // Cropper.getData() retorna {x, y, width, height} em pixels da imagem original
  const data = cropperState.instance.getData(true);  // rounded
  const payload = {
    job_id:    state.jobId,
    sku_base:  cropperState.sku_base,
    image_url: cropperState.image_url,
    crop: { x: data.x, y: data.y, width: data.width, height: data.height },
  };

  cropperSave.disabled = true;
  const lbl = cropperSave.textContent;
  cropperSave.textContent = 'Salvando...';

  try {
    const res = await fetch('/api/recrop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) {
      alert(`Erro: ${json.detail || 'desconhecido'}`);
      return;
    }
    // Atualiza thumbnail no grid sem refetch
    const itemEl = reviewGrid.querySelector(`.review-item[data-sku="${cropperState.sku_base}"]`);
    if (itemEl) {
      const img = itemEl.querySelector('.review-thumb');
      if (img) img.src = json.nova_url + (json.nova_url.includes('?') ? '&' : '?') + 't=' + Date.now();
    }
    fecharCropper();
  } catch (err) {
    alert(`Erro de rede: ${err.message || err}`);
  } finally {
    cropperSave.disabled = false;
    cropperSave.textContent = lbl;
  }
}

function mostrarErro(msg, avisos) {
  errorMsg.textContent = msg;

  const box = document.getElementById('error-avisos-box');
  const lista = document.getElementById('error-avisos-lista');
  if (box && lista) {
    if (avisos && avisos.length) {
      lista.innerHTML = '';
      avisos.forEach(av => {
        const li = document.createElement('li');
        li.textContent = av;
        lista.appendChild(li);
      });
      box.style.display = '';
    } else {
      box.style.display = 'none';
    }
  }

  mostrarSecao('error');
}

function baixarArquivo(tipo) {
  if (!state.jobId) return;
  const a = document.createElement('a');
  a.href = `/api/download/${state.jobId}/${tipo}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function resetar() {
  pararPolling();
  state.loja      = null;
  state.categoria = null;
  state.modo      = null;
  state.arquivo   = null;
  state.jobId     = null;

  lojasGrid.querySelectorAll('.loja-card').forEach(c => {
    c.classList.remove('selecionada');
    c.setAttribute('aria-pressed', 'false');
  });

  // Esconder/limpar sub-selecao de categoria
  if (categoriasGrid) categoriasGrid.innerHTML = '';
  if (categoriasRow) categoriasRow.style.display = 'none';

  // Limpar seleção de modo
  document.querySelectorAll('input[name="modo"]').forEach(r => { r.checked = false; });
  document.querySelectorAll('.modo-card').forEach(c => c.classList.remove('selecionado'));

  fileInput.value           = '';
  fileSelected.style.display = 'none';
  fileName.textContent       = '';
  atualizarBotao();
  atualizarProgresso('Aguardando início...', 0);
  mostrarSecao('form');
}

/* ── Tema (light/dark) ──────────────────────────────────────────────────── */
function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema;
  try { localStorage.setItem('theme', tema); } catch {}
}

function inicializarTema() {
  const btn = $('theme-toggle');
  if (!btn) return;
  // O tema inicial já foi aplicado pelo script inline no <head> (anti-flash).
  btn.addEventListener('click', () => {
    const atual = document.documentElement.dataset.theme || 'light';
    aplicarTema(atual === 'dark' ? 'light' : 'dark');
  });
}

/* ── Card de Desconto (fluxo 2-etapas independente) ─────────────────────── */
function configurarDesconto() {
  if (!btnDesconto || !descontoFileInput) return;  // card pode nao existir em telas antigas

  descontoFileBtn?.addEventListener('click', () => descontoFileInput.click());

  descontoFileInput.addEventListener('change', () => {
    const f = descontoFileInput.files[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.xlsx')) {
      mostrarStatusDesconto('Arquivo deve ser .xlsx (exportado da Shopee Seller Center)', 'error');
      descontoState.arquivo = null;
      btnDesconto.disabled = true;
      descontoFilename.textContent = '';
      return;
    }
    descontoState.arquivo = f;
    descontoFilename.textContent = f.name;
    btnDesconto.disabled = false;
    mostrarStatusDesconto('', null);
  });

  btnDesconto.addEventListener('click', gerarDesconto);
}

async function gerarDesconto() {
  if (!descontoState.arquivo) return;

  const fd = new FormData();
  fd.append('arquivo', descontoState.arquivo);

  btnDesconto.disabled = true;
  const labelOriginal = btnDesconto.textContent;
  btnDesconto.textContent = 'Gerando...';
  mostrarStatusDesconto('Lendo planilha da Shopee e fazendo lookup dos preços...', null);

  try {
    const res = await fetch('/api/desconto', { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Erro ao gerar planilha de desconto.';
      try {
        const data = await res.json();
        if (data?.detail) msg = data.detail;
      } catch { /* not JSON */ }
      mostrarStatusDesconto(msg, 'error');
      return;
    }

    // Sucesso — extrair filename do Content-Disposition + baixar
    const blob = await res.blob();
    const dispo = res.headers.get('Content-Disposition') || '';
    const m = dispo.match(/filename="?([^"]+)"?/);
    const filename = m ? m[1] : `discount_25off.xlsx`;

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    const avisosCount = parseInt(res.headers.get('X-Avisos-Count') || '0', 10);
    if (avisosCount > 0) {
      const avisos = (res.headers.get('X-Avisos') || '').split('|').filter(Boolean);
      mostrarStatusDesconto(
        `Pronto! ${avisosCount} SKU(s) sem lookup (preço vazio nessas linhas): ${avisos.slice(0, 2).join('; ')}${avisosCount > 2 ? '...' : ''}`,
        'success'
      );
    } else {
      mostrarStatusDesconto('Planilha de desconto gerada e baixada com sucesso.', 'success');
    }
  } catch (err) {
    mostrarStatusDesconto(`Não foi possível conectar ao servidor: ${err.message || err}`, 'error');
  } finally {
    btnDesconto.disabled = false;
    btnDesconto.textContent = labelOriginal;
  }
}

function mostrarStatusDesconto(msg, tipo) {
  if (!descontoStatus) return;
  descontoStatus.textContent = msg;
  descontoStatus.classList.remove('success', 'error');
  if (tipo === 'success') descontoStatus.classList.add('success');
  if (tipo === 'error')   descontoStatus.classList.add('error');
  descontoStatus.style.display = msg ? 'block' : 'none';
}

/* ── Banco de SKUs em uso ─────────────────────────────────────────────── */
function configurarSkusViewer() {
  if (btnAbrirSkus) btnAbrirSkus.addEventListener('click', abrirSkus);
  if (btnFecharSkus) btnFecharSkus.addEventListener('click', fecharSkus);
  if (skusBusca) skusBusca.addEventListener('input', () => {
    skusState.filtroBusca = skusBusca.value.trim().toLowerCase();
    renderizarSkus();
  });
  if (skusLojasFiltro) {
    skusLojasFiltro.querySelectorAll('.skus-filtro-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        skusLojasFiltro.querySelectorAll('.skus-filtro-pill').forEach(p =>
          p.classList.remove('selecionada'));
        pill.classList.add('selecionada');
        skusState.filtroLoja = pill.dataset.loja || '';
        renderizarSkus();
      });
    });
  }
  if (skusSort) {
    skusSort.addEventListener('change', () => {
      skusState.sort = skusSort.value || 'criado_desc';
      carregarSkus();  // refetch — ordenacao acontece no backend
    });
  }
}

function abrirSkus() {
  // Esconde tudo da home; mostra a tela de SKUs
  if (formSection)     formSection.style.display = 'none';
  if (progressSection) progressSection.style.display = 'none';
  if (resultSection)   resultSection.style.display = 'none';
  if (errorSection)    errorSection.style.display = 'none';
  if (btnProcessar)    btnProcessar.style.display = 'none';
  const desc = $('desconto-section');
  if (desc) desc.style.display = 'none';
  if (skusEntrySection) skusEntrySection.style.display = 'none';
  skusSection.style.display = 'flex';
  carregarSkus();
}

function fecharSkus() {
  skusSection.style.display = 'none';
  // Reseta a UI pro form inicial
  if (formSection)     formSection.style.display = 'contents';
  if (btnProcessar)    btnProcessar.style.display = 'flex';
  const desc = $('desconto-section');
  if (desc) desc.style.display = '';
  if (skusEntrySection) skusEntrySection.style.display = '';
}

async function carregarSkus() {
  skusStatus.textContent = 'Carregando…';
  skusStatus.classList.remove('error');
  skusTbody.innerHTML = '';
  try {
    const url = `/api/skus?sort=${encodeURIComponent(skusState.sort || 'criado_desc')}`;
    const res  = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao carregar SKUs');
    skusState.todos = data.skus || [];
    skusStatus.textContent =
      `${data.total} SKU${data.total !== 1 ? 's' : ''} • backend: ${data.backend}`;
    renderizarSkus();
  } catch (err) {
    skusState.todos = [];
    skusStatus.textContent = `Erro: ${err.message || err}`;
    skusStatus.classList.add('error');
  }
}

function skuMatchFiltro(sku) {
  if (skusState.filtroLoja && !sku.lojas.includes(skusState.filtroLoja)) return false;
  if (skusState.filtroBusca) {
    const q = skusState.filtroBusca;
    const skuCheio = sku.tipo ? `${sku.tipo}_${sku.sku_base}` : sku.sku_base;
    if (!skuCheio.toLowerCase().includes(q) &&
        !(sku.display || '').toLowerCase().includes(q)) return false;
  }
  return true;
}

function renderizarSkus() {
  const filtrados = skusState.todos.filter(skuMatchFiltro);
  skusTbody.innerHTML = '';
  if (!filtrados.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="6" class="skus-empty">Nenhum SKU corresponde aos filtros.</td>';
    skusTbody.appendChild(tr);
    return;
  }
  filtrados.forEach(sku => {
    const tr = document.createElement('tr');
    tr.dataset.sku = sku.sku_base;
    const lojasChips = sku.lojas.map(loja => `
      <span class="loja-chip">
        ${loja}
        <button type="button" class="loja-chip-x" data-loja="${loja}"
                title="Remover apenas '${loja}'">×</button>
      </span>
    `).join('');
    tr.innerHTML = `
      <td class="sku-base">${sku.tipo ? `${sku.tipo}_${sku.sku_base}` : sku.sku_base}</td>
      <td>${lojasChips}</td>
      <td>${sku.tipo}</td>
      <td>${sku.display || ''}</td>
      <td class="sku-data">${sku.criado_em || ''}</td>
      <td>
        <button type="button" class="btn-link-danger btn-apagar-sku">Apagar</button>
      </td>
    `;
    // Apagar SKU inteiro
    tr.querySelector('.btn-apagar-sku').addEventListener('click', () =>
      apagarSku(sku.sku_base));
    // Remover loja individual
    tr.querySelectorAll('.loja-chip-x').forEach(btn => {
      btn.addEventListener('click', () =>
        removerLojaDoSku(sku.sku_base, btn.dataset.loja));
    });
    skusTbody.appendChild(tr);
  });
}

async function apagarSku(skuBase) {
  if (!confirm(`Apagar SKU "${skuBase}" completamente? Isso libera o nome pra reuso.`))
    return;
  try {
    const res = await fetch(`/api/skus/${encodeURIComponent(skuBase)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falhou');
    // Remove do estado local sem refazer fetch
    skusState.todos = skusState.todos.filter(s => s.sku_base !== skuBase);
    renderizarSkus();
    skusStatus.textContent = `SKU "${skuBase}" apagado. ${skusState.todos.length} SKUs restantes.`;
  } catch (err) {
    alert(`Erro ao apagar: ${err.message || err}`);
  }
}

async function removerLojaDoSku(skuBase, loja) {
  if (!confirm(`Remover apenas "${loja}" do SKU "${skuBase}"? Se for a última loja, o SKU será apagado.`))
    return;
  try {
    const res = await fetch(
      `/api/skus/${encodeURIComponent(skuBase)}/loja/${encodeURIComponent(loja)}`,
      { method: 'DELETE' }
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falhou');
    // Recarrega pra refletir o estado correto (array pode ter ficado vazio ou nao)
    await carregarSkus();
  } catch (err) {
    alert(`Erro: ${err.message || err}`);
  }
}

/* ── Banco Kakashi ────────────────────────────────────────────────────── */
function configurarKakashiViewer() {
  if (btnAbrirKakashi)  btnAbrirKakashi.addEventListener('click', abrirKakashi);
  if (btnFecharKakashi) btnFecharKakashi.addEventListener('click', fecharKakashi);
  if (kakashiBusca) kakashiBusca.addEventListener('input', () => {
    kakashiState.filtroBusca = kakashiBusca.value.trim();
    carregarKakashi();
  });
  if (kakashiLojasFiltro) {
    kakashiLojasFiltro.querySelectorAll('.skus-filtro-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        kakashiLojasFiltro.querySelectorAll('.skus-filtro-pill').forEach(p =>
          p.classList.remove('selecionada'));
        pill.classList.add('selecionada');
        kakashiState.filtroLoja = pill.dataset.loja || '';
        carregarKakashi();
      });
    });
  }
  if (kakashiStatusFiltro) {
    kakashiStatusFiltro.querySelectorAll('.skus-filtro-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        kakashiStatusFiltro.querySelectorAll('.skus-filtro-pill').forEach(p =>
          p.classList.remove('selecionada'));
        pill.classList.add('selecionada');
        kakashiState.filtroStatus = pill.dataset.status || 'pendente';
        carregarKakashi();
      });
    });
  }
  if (kakashiSort) {
    kakashiSort.addEventListener('change', () => {
      kakashiState.sort = kakashiSort.value || 'criado_desc';
      carregarKakashi();
    });
  }
  if (kakashiCheckAll) {
    kakashiCheckAll.addEventListener('change', () => {
      const marcar = kakashiCheckAll.checked;
      kakashiState.todos.forEach(a => {
        if (marcar) kakashiState.selecionados.add(a.sku_base);
        else kakashiState.selecionados.delete(a.sku_base);
      });
      // Atualiza checkboxes do DOM sem refazer fetch
      kakashiTbody.querySelectorAll('input[type="checkbox"][data-sku]').forEach(c => {
        c.checked = marcar;
        c.closest('tr')?.classList.toggle('selecionada', marcar);
      });
      atualizarSelecaoKakashi();
    });
  }
  if (btnBaixarKakashi) btnBaixarKakashi.addEventListener('click', baixarKakashiSelecionados);
}

function abrirKakashi() {
  if (formSection)     formSection.style.display = 'none';
  if (progressSection) progressSection.style.display = 'none';
  if (resultSection)   resultSection.style.display = 'none';
  if (errorSection)    errorSection.style.display = 'none';
  if (btnProcessar)    btnProcessar.style.display = 'none';
  const desc = $('desconto-section');
  if (desc) desc.style.display = 'none';
  if (skusEntrySection)    skusEntrySection.style.display = 'none';
  if (kakashiEntrySection) kakashiEntrySection.style.display = 'none';
  kakashiSection.style.display = 'flex';
  carregarKakashi();
}

function fecharKakashi() {
  kakashiSection.style.display = 'none';
  if (formSection)     formSection.style.display = 'contents';
  if (btnProcessar)    btnProcessar.style.display = 'flex';
  const desc = $('desconto-section');
  if (desc) desc.style.display = '';
  if (skusEntrySection)    skusEntrySection.style.display = '';
  if (kakashiEntrySection) kakashiEntrySection.style.display = '';
}

async function carregarKakashi() {
  kakashiStatusInfo.textContent = 'Carregando…';
  kakashiStatusInfo.classList.remove('error');
  kakashiTbody.innerHTML = '';
  if (kakashiCheckAll) kakashiCheckAll.checked = false;
  try {
    const params = new URLSearchParams({
      sort:   kakashiState.sort || 'criado_desc',
      status: kakashiState.filtroStatus || 'pendente',
    });
    if (kakashiState.filtroLoja)  params.set('loja', kakashiState.filtroLoja);
    if (kakashiState.filtroBusca) params.set('q', kakashiState.filtroBusca);
    const res  = await fetch(`/api/kakashi?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao carregar artes Kakashi');
    kakashiState.todos = data.artes || [];
    kakashiStatusInfo.textContent =
      `${data.total} arte${data.total !== 1 ? 's' : ''} • backend: ${data.backend} • filtro: ${data.status}`;
    renderizarKakashi();
  } catch (err) {
    kakashiState.todos = [];
    kakashiStatusInfo.textContent = `Erro: ${err.message || err}`;
    kakashiStatusInfo.classList.add('error');
    atualizarSelecaoKakashi();
  }
}

function renderizarKakashi() {
  kakashiTbody.innerHTML = '';
  if (!kakashiState.todos.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="8" class="skus-empty">Nenhuma arte corresponde aos filtros.</td>';
    kakashiTbody.appendChild(tr);
    atualizarSelecaoKakashi();
    return;
  }
  kakashiState.todos.forEach(arte => {
    const tr = document.createElement('tr');
    tr.dataset.sku = arte.sku_base;
    const selecionado = kakashiState.selecionados.has(arte.sku_base);
    if (selecionado) tr.classList.add('selecionada');
    const enviado = !!arte.enviado_kakashi_em;
    const statusHtml = enviado
      ? `<span class="kakashi-badge kakashi-badge-enviado" title="Clique pra reverter">Enviado ${arte.enviado_kakashi_em}</span>`
      : `<span class="kakashi-badge kakashi-badge-pendente" title="Clique pra marcar como enviado">Pendente</span>`;
    tr.innerHTML = `
      <td><input type="checkbox" data-sku="${arte.sku_base}" ${selecionado ? 'checked' : ''}></td>
      <td><img class="kakashi-thumb" src="${arte.imagem_capa}" alt="" loading="lazy"
              onerror="this.style.background='#fee'"></td>
      <td class="sku-base">${arte.sku_completo || arte.sku_base}</td>
      <td>${arte.descricao || ''}</td>
      <td>${arte.loja || ''}</td>
      <td class="sku-data">${arte.criado_em || ''}</td>
      <td>${statusHtml}</td>
      <td><button type="button" class="btn-link-danger btn-apagar-kakashi">Apagar</button></td>
    `;
    // Checkbox
    tr.querySelector('input[type="checkbox"]').addEventListener('change', (e) => {
      const sku = arte.sku_base;
      if (e.target.checked) {
        kakashiState.selecionados.add(sku);
        tr.classList.add('selecionada');
      } else {
        kakashiState.selecionados.delete(sku);
        tr.classList.remove('selecionada');
      }
      atualizarSelecaoKakashi();
    });
    // Toggle status (clica no badge)
    tr.querySelector('.kakashi-badge').addEventListener('click', () =>
      toggleStatusKakashi(arte.sku_base, !enviado));
    // Apagar
    tr.querySelector('.btn-apagar-kakashi').addEventListener('click', () =>
      apagarKakashi(arte.sku_base));
    kakashiTbody.appendChild(tr);
  });
  atualizarSelecaoKakashi();
}

function atualizarSelecaoKakashi() {
  const n = kakashiState.selecionados.size;
  if (kakashiSelecaoInfo) {
    kakashiSelecaoInfo.textContent = `${n} selecionado${n !== 1 ? 's' : ''}`;
  }
  if (btnBaixarKakashi) {
    btnBaixarKakashi.disabled = (n === 0);
    btnBaixarKakashi.textContent = `Baixar planilha (${n})`;
  }
}

async function toggleStatusKakashi(skuBase, enviado) {
  try {
    const res = await fetch(`/api/kakashi/${encodeURIComponent(skuBase)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enviado }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falhou');
    await carregarKakashi();
  } catch (err) {
    alert(`Erro ao atualizar status: ${err.message || err}`);
  }
}

async function apagarKakashi(skuBase) {
  if (!confirm(`Apagar a arte "${skuBase}" do banco Kakashi? (não afeta o banco de SKUs nem a Shopee)`))
    return;
  try {
    const res = await fetch(`/api/kakashi/${encodeURIComponent(skuBase)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falhou');
    kakashiState.selecionados.delete(skuBase);
    await carregarKakashi();
  } catch (err) {
    alert(`Erro ao apagar: ${err.message || err}`);
  }
}

async function baixarKakashiSelecionados() {
  if (kakashiState.selecionados.size === 0) return;
  const skus = [...kakashiState.selecionados];
  const labelOriginal = btnBaixarKakashi.textContent;
  btnBaixarKakashi.disabled = true;
  btnBaixarKakashi.textContent = 'Baixando…';
  try {
    const res = await fetch('/api/kakashi/baixar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sku_bases: skus }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const dispo = res.headers.get('Content-Disposition') || '';
    const m = dispo.match(/filename="([^"]+)"/);
    a.download = m ? m[1] : 'kakashi_selecao.xlsx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    // Limpa selecao e re-fetch (artes agora viraram 'enviado')
    kakashiState.selecionados.clear();
    await carregarKakashi();
  } catch (err) {
    alert(`Erro ao baixar: ${err.message || err}`);
    btnBaixarKakashi.disabled = false;
    btnBaixarKakashi.textContent = labelOriginal;
  }
}
