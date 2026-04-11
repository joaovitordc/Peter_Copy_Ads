/* ── Estado ────────────────────────────────────────────────────────────── */
const state = {
  loja:         null,
  modo:         'links_com_imagens',
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
const btnProcessar   = $('btn-processar');

const formSection     = $('form-section');
const progressSection = $('progress-section');
const resultSection   = $('result-section');
const errorSection    = $('error-section');

const progressLabel   = $('progress-label');
const progressPct     = $('progress-pct');
const progressBarFill = $('progress-bar-fill');
const progressBar     = progressSection?.querySelector('[role=progressbar]');

const resultSubtitle    = $('result-subtitle');
const btnDownloadShopee = $('btn-download-shopee');
const btnDownloadErp    = $('btn-download-erp');
const avisosBox         = $('avisos-box');
const avisosLista       = $('avisos-lista');
const btnNovaPlanilha   = $('btn-nova-planilha');

const errorMsg           = $('error-msg');
const btnTentarNovamente = $('btn-tentar-novamente');

/* ── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  carregarLojas();
  configurarModos();
  configurarDropzone();
  configurarBotoes();
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
      { id: 'AllQuadros', nome: 'AllQuadros', descricao: 'Kits e conjuntos decorativos' },
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
}

function atualizarBotao() {
  btnProcessar.disabled = !(state.loja && state.arquivo);
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
    else if (data.status === 'erro') { pararPolling(); mostrarErro(data.erro || data.mensagem || 'Erro desconhecido.'); }
  } catch { /* retry na próxima iteração */ }
}

/* ── UI ─────────────────────────────────────────────────────────────────── */
function mostrarSecao(secao) {
  formSection.style.display     = secao === 'form'     ? '' : 'none';
  progressSection.style.display = secao === 'progress' ? '' : 'none';
  resultSection.style.display   = secao === 'result'   ? '' : 'none';
  errorSection.style.display    = secao === 'error'    ? '' : 'none';
  btnProcessar.style.display    = secao === 'form'     ? '' : 'none';
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

function mostrarErro(msg) {
  errorMsg.textContent = msg;
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
  state.arquivo = null;
  state.jobId   = null;

  lojasGrid.querySelectorAll('.loja-card').forEach(c => {
    c.classList.remove('selecionada');
    c.setAttribute('aria-pressed', 'false');
  });

  // Resetar modo para padrão
  const radioDefault = document.querySelector('input[name="modo"][value="links_com_imagens"]');
  if (radioDefault) {
    radioDefault.checked = true;
    state.modo = 'links_com_imagens';
    document.querySelectorAll('.modo-card').forEach(card => {
      const inp = card.querySelector('input[name="modo"]');
      card.classList.toggle('selecionado', inp?.value === 'links_com_imagens');
    });
  }

  fileInput.value           = '';
  fileSelected.style.display = 'none';
  fileName.textContent       = '';
  atualizarBotao();
  atualizarProgresso('Aguardando início...', 0);
  mostrarSecao('form');
  btnProcessar.style.display = '';
}
