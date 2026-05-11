/* ── Estado ────────────────────────────────────────────────────────────── */
const state = {
  loja:         null,
  modo:         null,
  arquivo:      null,
  jobId:        null,
  pollingTimer: null,
};

/* ── Helpers DOM ───────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const lojasGrid      = $('lojas-grid');
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
const btnDownloadShopee  = $('btn-download-shopee');
const btnDownloadErp     = $('btn-download-erp');
const btnDownloadKakashi = $('btn-download-kakashi');
const avisosBox         = $('avisos-box');
const avisosLista       = $('avisos-lista');
const btnNovaPlanilha   = $('btn-nova-planilha');

const errorMsg           = $('error-msg');
const btnTentarNovamente = $('btn-tentar-novamente');

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  inicializarTema();
  carregarLojas();
  configurarModos();
  configurarDropzone();
  configurarBotoes();
  atualizarPainelPreview();
  atualizarPainelTips();
  atualizarPainelStatus();
});

/* ── Lojas ──────────────────────────────────────────────────────────────── */
async function carregarLojas() {
  try {
    const res  = await fetch('/api/lojas');
    const data = await res.json();
    renderizarLojas(data.lojas || []);
  } catch {
    renderizarLojas([
      { id: 'PPJ',        nome: 'PPJ',        descricao: 'Quadros religiosos e minimalistas' },
      { id: 'iPaper',     nome: 'iPaper',     descricao: 'Arte, Bauhaus e design moderno' },
      { id: 'AllQuadros', nome: 'AllQuadros', descricao: 'Moderno, minimalista, boho' },
      { id: 'DecorKids',  nome: 'DecorKids',  descricao: 'Quadros para decoração infantil' },
    ]);
  }
}

function renderizarLojas(lojas) {
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
  atualizarBotao();
  atualizarPainelStatus();
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
      atualizarPainelPreview();
      atualizarPainelTips();
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
  atualizarPainelStatus();
}

/* ── Botões ─────────────────────────────────────────────────────────────── */
function configurarBotoes() {
  btnProcessar.addEventListener('click', iniciarProcessamento);
  btnNovaPlanilha?.addEventListener('click', resetar);
  btnTentarNovamente?.addEventListener('click', resetar);
  btnDownloadShopee?.addEventListener('click', () => baixarArquivo('shopee'));
  btnDownloadErp?.addEventListener('click', () => baixarArquivo('erp'));
  btnDownloadKakashi?.addEventListener('click', () => baixarArquivo('kakashi'));
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
  atualizarPainelStatus(secao);
}

function atualizarProgresso(mensagem, pct) {
  progressLabel.textContent     = mensagem;
  progressPct.textContent       = `${pct}%`;
  progressBarFill.style.width   = `${pct}%`;
  if (progressBar) progressBar.setAttribute('aria-valuenow', String(pct));
}

function mostrarResultado(data) {
  const n = data.produtos || 0;
  resultSubtitle.textContent = `${n} produto${n !== 1 ? 's' : ''} processado${n !== 1 ? 's' : ''} com sucesso.`;

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
  state.loja   = null;
  state.modo   = null;
  state.arquivo = null;
  state.jobId   = null;

  lojasGrid.querySelectorAll('.loja-card').forEach(c => {
    c.classList.remove('selecionada');
    c.setAttribute('aria-pressed', 'false');
  });

  // Limpar seleção de modo
  document.querySelectorAll('input[name="modo"]').forEach(r => { r.checked = false; });
  document.querySelectorAll('.modo-card').forEach(c => c.classList.remove('selecionado'));

  fileInput.value           = '';
  fileSelected.style.display = 'none';
  fileName.textContent       = '';
  atualizarBotao();
  atualizarProgresso('Aguardando início...', 0);
  atualizarPainelPreview();
  atualizarPainelTips();
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

/* ── Painel direito ─────────────────────────────────────────────────────── */
function atualizarPainelStatus(secao) {
  const items = document.querySelectorAll('.info-status-item');
  if (!items.length) return;

  const checks = {
    loja:       Boolean(state.loja),
    modo:       Boolean(state.modo),
    arquivo:    Boolean(state.arquivo),
    processar:  secao === 'result',
  };

  // Primeiro passo não-completo é o ativo
  let ativo = null;
  if (!checks.loja) ativo = 'loja';
  else if (!checks.modo) ativo = 'modo';
  else if (!checks.arquivo) ativo = 'arquivo';
  else if (secao === 'progress') ativo = 'processar';
  else if (secao !== 'result') ativo = 'processar';

  items.forEach(item => {
    const step = item.dataset.step;
    item.classList.toggle('done', Boolean(checks[step]));
    item.classList.toggle('active', step === ativo);
  });
}

function atualizarPainelPreview() {
  const el = $('info-preview-content');
  if (!el) return;

  if (!state.modo) {
    el.innerHTML = `
      <p class="info-card-body">
        Escolha um tipo de planilha no passo 2 para ver o formato esperado.
      </p>
    `;
    return;
  }

  const isComImagens = state.modo === 'links_com_imagens';

  const headerCells = isComImagens
    ? ['Qtd', 'Link Etsy', 'Img 1', 'Img 2', 'Img 3', 'Img 4']
    : ['Qtd', 'Link Etsy'];

  const sampleRow = isComImagens
    ? ['1',  'etsy.com/...', 'i.imgbb...', 'i.imgbb...', 'i.imgbb...', 'i.imgbb...']
    : ['1',  'etsy.com/listing/...'];

  const cols = isComImagens
    ? '40px 1fr 60px 60px 60px 60px'
    : '50px 1fr';

  el.innerHTML = `
    <div class="info-preview-table" role="presentation">
      <div class="info-preview-row header" style="grid-template-columns: ${cols}">
        ${headerCells.map(c => `<div class="info-preview-cell">${c}</div>`).join('')}
      </div>
      <div class="info-preview-row" style="grid-template-columns: ${cols}">
        ${sampleRow.map(c => `<div class="info-preview-cell">${c}</div>`).join('')}
      </div>
      <div class="info-preview-row" style="grid-template-columns: ${cols}">
        ${sampleRow.map(c => `<div class="info-preview-cell">${c}</div>`).join('')}
      </div>
    </div>
    <p class="info-card-body" style="margin-top: 0.625rem;">
      ${isComImagens
        ? 'Cada linha = 1 anúncio. Imagens já pré-selecionadas pelo operador.'
        : 'Apenas o link — Peter busca título e imagens automaticamente.'}
    </p>
  `;
}

function atualizarPainelTips() {
  const el = $('info-tips-list');
  if (!el) return;

  const tipsBase = [
    'A coluna "Qtd" (1-9) define o tipo do produto. Vazia = detecção automática.',
    'O modo "Links + Imagens" é mais rápido e estável (sem APIs externas).',
  ];

  const tipsLinks = [
    'O modo "Só Links" leva 3-5 min por anúncio (Firecrawl + filtro Gemini).',
    'Free tier do Firecrawl é 5 chamadas/dia — para volume, faça upgrade.',
  ];

  const tips = state.modo === 'links' ? tipsLinks : tipsBase;

  el.innerHTML = tips.map(t => `
    <li class="info-tips-item">
      <span class="tip-bullet" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="2.5" fill="currentColor"/>
        </svg>
      </span>
      <span>${t}</span>
    </li>
  `).join('');
}
