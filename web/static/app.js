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

// Revisão de capas (Opção A — thumbnails + descarte)
const reviewSection = $('review-section');
const reviewGrid    = $('review-grid');
const reviewStatus  = $('review-status');
const btnDescartar  = $('btn-descartar');
const descartadosSet = new Set();  // SKUs base marcados pra descartar
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
const skusTbody        = $('skus-tbody');
const skusStatus       = $('skus-status');
const skusState        = { todos: [], filtroLoja: '', filtroBusca: '' };

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  inicializarTema();
  carregarLojas();
  configurarModos();
  configurarDropzone();
  configurarBotoes();
  configurarDesconto();
  configurarSkusViewer();
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

    if (data.status === 'concluido') { pararPolling(); mostrarResultado(data); }
    else if (data.status === 'erro') { pararPolling(); mostrarErro(data.erro || data.mensagem || 'Erro desconhecido.', data.avisos); }
  } catch { /* retry na próxima iteração */ }
}

/* ── UI ─────────────────────────────────────────────────────────────────── */
function mostrarSecao(secao) {
  // formSection é um wrapper com display: contents (ver HTML) — preserva o grid
  formSection.style.display     = secao === 'form'     ? 'contents' : 'none';
  progressSection.style.display = secao === 'progress' ? 'flex'     : 'none';
  resultSection.style.display   = secao === 'result'   ? 'flex'     : 'none';
  errorSection.style.display    = secao === 'error'    ? 'block'    : 'none';
  btnProcessar.style.display    = secao === 'form'     ? 'flex'     : 'none';
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

  // Carrega thumbnails de capa pra revisão (Opção A)
  if (state.jobId) carregarRevisaoCapas(state.jobId);
}

/* ── Revisão de capas (Opção A — thumbnails + descarte) ────────────────── */
async function carregarRevisaoCapas(jobId) {
  if (!reviewSection || !reviewGrid) return;
  try {
    const res = await fetch(`/api/produtos/${jobId}`);
    if (!res.ok) { reviewSection.style.display = 'none'; return; }
    const data = await res.json();
    if (!data.suporte_descarte || !data.produtos?.length) {
      reviewSection.style.display = 'none';
      return;
    }
    renderizarRevisao(data.produtos);
    reviewSection.style.display = '';
  } catch {
    reviewSection.style.display = 'none';
  }
}

function renderizarRevisao(produtos) {
  reviewGrid.innerHTML = '';
  descartadosSet.clear();

  produtos.forEach(p => {
    const item = document.createElement('label');
    item.className = 'review-item';
    item.dataset.sku = p.sku_base;
    item.innerHTML = `
      <input type="checkbox" aria-label="Descartar ${p.sku_completo}">
      <img src="${p.imagem_capa}" alt="Capa ${p.display}" loading="lazy"
           onerror="this.style.background='#fee'; this.alt='Capa não carregou'">
      <div class="review-info">
        <span class="review-sku">${p.sku_completo}</span>
        <span class="review-display">${p.display}</span>
      </div>
    `;
    const chk = item.querySelector('input');
    chk.addEventListener('change', () => {
      if (chk.checked) {
        descartadosSet.add(p.sku_base);
        item.classList.add('descartar');
      } else {
        descartadosSet.delete(p.sku_base);
        item.classList.remove('descartar');
      }
      atualizarBotaoDescartar();
    });
    reviewGrid.appendChild(item);
  });
  atualizarBotaoDescartar();

  if (btnDescartar && !btnDescartar.dataset.bound) {
    btnDescartar.addEventListener('click', aplicarDescarte);
    btnDescartar.dataset.bound = '1';
  }
}

function atualizarBotaoDescartar() {
  const n = descartadosSet.size;
  if (btnDescartar) btnDescartar.disabled = (n === 0);
  if (reviewStatus) {
    reviewStatus.textContent = n === 0
      ? 'Nenhum descarte marcado'
      : `${n} produto${n !== 1 ? 's' : ''} marcado${n !== 1 ? 's' : ''} pra descarte`;
  }
}

async function aplicarDescarte() {
  if (!state.jobId || descartadosSet.size === 0) return;
  const skus = [...descartadosSet];
  if (!confirm(`Confirma descartar ${skus.length} produto(s)? As planilhas serão regeneradas sem eles e os SKUs ficarão liberados pra reuso.`)) return;

  btnDescartar.disabled = true;
  const labelOriginal = btnDescartar.textContent;
  btnDescartar.textContent = 'Regenerando...';

  try {
    const res = await fetch('/api/descartar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: state.jobId, skus_base: skus }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Erro: ${data.detail || 'desconhecido'}`);
      btnDescartar.disabled = false;
      btnDescartar.textContent = labelOriginal;
      return;
    }
    // Sucesso — recarrega o grid sem os descartados + atualiza subtitle
    alert(data.mensagem || 'Descarte aplicado.');
    if (resultSubtitle) {
      resultSubtitle.textContent = `${data.produtos_ativos} produtos ativos (${data.descartados} descartados nesta sessão).`;
    }
    carregarRevisaoCapas(state.jobId);  // re-renderiza o grid (sem descartados)
  } catch (err) {
    alert(`Erro de rede: ${err.message || err}`);
    btnDescartar.disabled = false;
    btnDescartar.textContent = labelOriginal;
  } finally {
    btnDescartar.textContent = labelOriginal;
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
    const res  = await fetch('/api/skus');
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
