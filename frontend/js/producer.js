/**
 * Painel do Produtor: CRUD de Produtos, Gestão de Pedidos, Resumo de Vendas, Avaliações e Propriedade.
 */
import { apiFetch, parseError } from './api.js';
import { statusLabels } from './orders.js';
import { clearFormError, escapeHtml, formatCurrency, formatDate, openModal, safeUrl, showFormError, showToast } from './ui.js';

let producerProductsCache = [];

export async function openProducerPanel(initialTab = 'produtos') {
  openModal('producerPanelModalOverlay');
  switchProducerTab(initialTab);
}

export function switchProducerTab(tab) {
  const tabs = ['produtos', 'pedidos', 'vendas', 'propriedade'];
  tabs.forEach(t => {
    const cap = t.charAt(0).toUpperCase() + t.slice(1);
    document.querySelector(`.panel-tab[data-producer-tab="${t}"]`)?.classList.toggle('active', t === tab);
    const panel = document.getElementById(`producerTab${cap}`);
    if (panel) panel.style.display = t === tab ? 'block' : 'none';
  });

  if (tab === 'produtos') {
    loadProducerCategoriesSelect();
    loadProducerProducts();
  } else if (tab === 'pedidos') {
    loadProducerOrders();
  } else if (tab === 'vendas') {
    loadProducerSalesAndReviews();
  } else if (tab === 'propriedade') {
    loadProducerProperty();
  }
}

async function loadProducerCategoriesSelect() {
  const sel = document.getElementById('prodCategoria');
  if (!sel) return;
  try {
    const res = await apiFetch('/categorias/');
    if (!res.ok) return;
    const data = await res.json();
    const cats = (data.results || data || []).filter(c => c.ativa !== false);
    sel.innerHTML = cats.map(c => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`).join('');
  } catch (_) {}
}

export async function loadProducerProducts() {
  const list = document.getElementById('producerProductsList');
  if (!list) return;
  list.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/produtor/produtos/');
    if (!res.ok) throw new Error('Falha ao carregar seus produtos.');
    const data = await res.json();
    producerProductsCache = data.results || data || [];

    if (producerProductsCache.length === 0) {
      list.innerHTML = '<div class="empty-state"><p>Você ainda não cadastrou produtos. Clique em "Novo Produto".</p></div>';
      return;
    }

    list.innerHTML = producerProductsCache.map(p => {
      const img = safeUrl(p.imagem, '/static/assets/logo-icon.webp');
      return `
        <div class="panel-list-item">
          <img src="${escapeHtml(img)}" alt="${escapeHtml(p.nome)}" class="panel-thumb" />
          <div class="panel-list-item__info">
            <strong>${escapeHtml(p.nome)}</strong>
            <span>${formatCurrency(p.preco)} / ${escapeHtml(p.unidade_medida)} • Estoque: ${parseFloat(p.estoque)}</span>
            <span class="badge ${p.ativo ? 'badge--success' : 'badge--outline'}">${p.ativo ? 'Ativo' : 'Oculto'}</span>
          </div>
          <div class="panel-list-item__actions">
            <button type="button" class="btn btn--outline btn--sm btnEditProdProduct" data-id="${p.id}">Editar</button>
            <button type="button" class="btn btn--outline btn--sm text-danger btnDeleteProdProduct" data-id="${p.id}">Excluir</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    list.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export function openProductForm(productId = null) {
  const wrap = document.getElementById('producerProductFormWrap');
  const form = document.getElementById('producerProductForm');
  if (!wrap || !form) return;
  clearFormError('producerProductError');
  form.reset();

  if (productId) {
    const p = producerProductsCache.find(x => String(x.id) === String(productId));
    if (p) {
      document.getElementById('prodId').value = String(p.id);
      document.getElementById('prodNome').value = p.nome || '';
      document.getElementById('prodCategoria').value = String(p.categoria || '');
      document.getElementById('prodPreco').value = String(p.preco || '');
      document.getElementById('prodUnidade').value = p.unidade_medida || 'UNIDADE';
      document.getElementById('prodEstoque').value = String(p.estoque || '0');
      document.getElementById('prodTipo').value = p.tipo_producao || 'ORGANICO_CERTIFICADO';
      document.getElementById('prodDescricao').value = p.descricao || '';
      document.getElementById('prodAtivo').checked = Boolean(p.ativo);
    }
  } else {
    document.getElementById('prodId').value = '';
    document.getElementById('prodAtivo').checked = true;
  }
  wrap.style.display = 'block';
}

export async function saveProducerProduct(formEl) {
  clearFormError('producerProductError');
  const id = document.getElementById('prodId').value;
  const fd = new FormData();
  fd.append('nome', document.getElementById('prodNome').value.trim());
  fd.append('categoria', document.getElementById('prodCategoria').value);
  fd.append('preco', document.getElementById('prodPreco').value.replace(',', '.'));
  fd.append('unidade_medida', document.getElementById('prodUnidade').value);
  fd.append('estoque', document.getElementById('prodEstoque').value.replace(',', '.'));
  fd.append('tipo_producao', document.getElementById('prodTipo').value);
  fd.append('descricao', document.getElementById('prodDescricao').value.trim());
  fd.append('ativo', document.getElementById('prodAtivo').checked ? 'true' : 'false');

  const fileInput = document.getElementById('prodImagem');
  if (fileInput?.files?.length > 0) {
    fd.append('imagem', fileInput.files[0]);
  }

  const endpoint = id ? `/produtor/produtos/${id}/` : '/produtor/produtos/';
  const method = id ? 'PATCH' : 'POST';

  const res = await apiFetch(endpoint, { method, body: fd });
  if (!res.ok) {
    const err = await parseError(res);
    showFormError('producerProductError', err);
    return;
  }

  document.getElementById('producerProductFormWrap').style.display = 'none';
  showToast(id ? 'Produto atualizado!' : 'Produto cadastrado!', 'success');
  await loadProducerProducts();
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}

export async function deleteProducerProduct(id) {
  if (!confirm('Deseja realmente excluir este produto?')) return;
  const res = await apiFetch(`/produtor/produtos/${id}/`, { method: 'DELETE' });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Produto excluído.', 'info');
  await loadProducerProducts();
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}

// ── Pedidos Recebidos pelo Produtor ─────────────────────────────────────────
export async function loadProducerOrders() {
  const container = document.getElementById('producerOrdersList');
  if (!container) return;
  container.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/produtor/pedidos/');
    if (!res.ok) throw new Error('Falha ao carregar pedidos.');
    const data = await res.json();
    const orders = data.results || data || [];

    if (orders.length === 0) {
      container.innerHTML = '<div class="empty-state"><p>Nenhum pedido recebido ainda.</p></div>';
      return;
    }

    container.innerHTML = orders.map(o => {
      const st = statusLabels[o.status] || { label: o.status, class: '' };
      let actions = '';
      if (o.status === 'PENDENTE') {
        actions = `
          <button type="button" class="btn btn--primary btn--sm btnProdOrderAction" data-id="${o.id}" data-action="aceitar">✓ Aceitar</button>
          <button type="button" class="btn btn--outline btn--sm text-danger btnProdOrderAction" data-id="${o.id}" data-action="recusar">✕ Recusar</button>
        `;
      } else if (o.status === 'ACEITO') {
        actions = `<button type="button" class="btn btn--primary btn--sm btnProdOrderAction" data-id="${o.id}" data-action="status" data-next="EM_PREPARO">🌱 Iniciar Preparo</button>`;
      } else if (o.status === 'EM_PREPARO') {
        actions = `<button type="button" class="btn btn--primary btn--sm btnProdOrderAction" data-id="${o.id}" data-action="status" data-next="PRONTO">📦 Marcar Pronto</button>`;
      } else if (o.status === 'PRONTO' && o.modalidade === 'RETIRADA') {
        actions = `<button type="button" class="btn btn--cta btn--sm btnProdOrderAction" data-id="${o.id}" data-action="status" data-next="CONCLUIDO">✅ Confirmar Retirada</button>`;
      }

      return `
        <div class="order-card">
          <div class="order-card__header">
            <div>
              <strong>${escapeHtml(o.numero_publico || `#${o.id}`)}</strong>
              <span class="text-muted">• Cliente: ${escapeHtml(o.cliente_nome || 'Cliente')}</span>
            </div>
            <span class="badge ${st.class}">${escapeHtml(st.label)}</span>
          </div>
          <div class="order-card__body">
            <p>${o.modalidade === 'ENTREGA' ? '🚚 Entrega' : '🏪 Retirada'} • ${escapeHtml(o.forma_pagamento)}</p>
            ${o.endereco_entrega ? `<p><strong>Endereço:</strong> ${escapeHtml(o.endereco_entrega)}</p>` : ''}
            ${o.observacao ? `<p><strong>Obs.:</strong> ${escapeHtml(o.observacao)}</p>` : ''}
            <ul class="order-items-list">
              ${(o.itens || []).map(it => `<li>${escapeHtml(it.nome_produto)} × ${parseFloat(it.quantidade)} ${escapeHtml(it.unidade_medida)}</li>`).join('')}
            </ul>
          </div>
          <div class="order-card__footer">
            <strong>${formatCurrency(o.total_com_frete || o.total)}</strong>
            <div class="order-card__actions">${actions}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export async function handleProducerOrderAction(orderId, action, nextStatus = '') {
  let endpoint = `/produtor/pedidos/${orderId}/${action}/`;
  let body = {};

  if (action === 'aceitar') {
    const previsao = prompt('Previsão de entrega/retirada (opcional, ex: Amanhã 09h-12h):');
    if (previsao === null) return;
    body = { previsao_entrega: previsao };
  } else if (action === 'recusar') {
    const motivo = prompt('Motivo da recusa:') || '';
    body = { motivo };
  } else if (action === 'status') {
    endpoint = `/produtor/pedidos/${orderId}/status/`;
    body = { status: nextStatus };
  }

  const res = await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(body) });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Status do pedido atualizado!', 'success');
  await loadProducerOrders();
}

// ── Vendas e Avaliações ────────────────────────────────────────────────────
async function loadProducerSalesAndReviews() {
  const el = document.getElementById('producerSalesContent');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const [resVendas, resAv] = await Promise.all([
      apiFetch('/produtor/pedidos/vendas/'),
      apiFetch('/produtor/avaliacoes/'),
    ]);
    const vendas = resVendas.ok ? await resVendas.json() : { quantidade_vendas: 0, faturamento: 0 };
    const avData = resAv.ok ? await resAv.json() : { results: [] };
    const avaliacoes = avData.results || [];

    el.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi-card">
          <span>Vendas Concluídas</span>
          <strong>${Number(vendas.quantidade_vendas) || 0}</strong>
        </div>
        <div class="kpi-card">
          <span>Faturamento Total</span>
          <strong>${formatCurrency(vendas.faturamento)}</strong>
        </div>
      </div>
      <h4 style="margin-block: var(--space-4) var(--space-2);">⭐ Avaliações Recebidas (${avaliacoes.length})</h4>
      ${avaliacoes.length === 0
        ? '<p class="text-muted">Nenhuma avaliação recebida ainda.</p>'
        : avaliacoes.map(a => `
          <div class="review-item">
            <div class="review-item__head">
              <strong>${escapeHtml(a.cliente_nome || 'Cliente')}</strong>
              <span>${'⭐'.repeat(a.nota)}</span>
            </div>
            <p>${escapeHtml(a.comentario || '')}</p>
            <span class="text-muted">${formatDate(a.criado_em)}</span>
          </div>
        `).join('')}
    `;
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

// ── Dados da Propriedade Rural ─────────────────────────────────────────────
async function loadProducerProperty() {
  try {
    const res = await apiFetch('/perfil/produtor/');
    if (!res.ok) return;
    const p = await res.json();

    const badge = document.getElementById('producerStatusBadge');
    if (badge) {
      badge.textContent = `Status: ${p.status}`;
      badge.className = `badge ${p.status === 'APROVADO' ? 'badge--success' : 'badge--outline'}`;
    }

    document.getElementById('propNome').value = p.nome_propriedade || '';
    document.getElementById('propDescricao').value = p.descricao || '';
    document.getElementById('propEndereco').value = p.endereco_propriedade || '';
    document.getElementById('propCidade').value = p.cidade || '';
    document.getElementById('propEstado').value = p.estado || '';
    document.getElementById('propChavePix').value = p.chave_pix || '';
    document.getElementById('propMaquininha').checked = Boolean(p.possui_maquininha);
    document.getElementById('propDinheiro').checked = Boolean(p.aceita_dinheiro);

    const previewImg = document.getElementById('propFotoPreviewImg');
    const previewText = document.getElementById('propFotoPreviewText');
    const customFoto = p.foto_propriedade ? safeUrl(p.foto_propriedade, '') : '';
    if (previewImg && previewText) {
      if (customFoto) {
        previewImg.src = customFoto;
        previewImg.classList.remove('producer-card__img--default');
        previewText.textContent = 'Foto atual da propriedade cadastrada. Selecione outro arquivo acima se quiser substituí-la.';
      } else {
        previewImg.src = '/static/assets/logo-icon.webp';
        previewImg.classList.add('producer-card__img--default');
        previewText.textContent = 'Usando logo padrão da Feira Virtual (envie uma foto para personalizar sua propriedade).';
      }
    }
  } catch (_) {}
}

export async function saveProducerProperty() {
  clearFormError('producerPropertyError');
  const fd = new FormData();
  fd.append('nome_propriedade', document.getElementById('propNome').value.trim());
  fd.append('descricao', document.getElementById('propDescricao').value.trim());
  fd.append('endereco_propriedade', document.getElementById('propEndereco').value.trim());
  fd.append('cidade', document.getElementById('propCidade').value.trim());
  fd.append('estado', document.getElementById('propEstado').value.trim().toUpperCase());
  fd.append('chave_pix', document.getElementById('propChavePix').value.trim());
  fd.append('possui_maquininha', document.getElementById('propMaquininha').checked ? 'true' : 'false');
  fd.append('aceita_dinheiro', document.getElementById('propDinheiro').checked ? 'true' : 'false');

  const foto = document.getElementById('propFoto');
  if (foto?.files?.length > 0) {
    fd.append('foto_propriedade', foto.files[0]);
  }

  const res = await apiFetch('/perfil/produtor/', { method: 'PATCH', body: fd });
  if (!res.ok) {
    showFormError('producerPropertyError', await parseError(res));
    return;
  }
  if (foto) foto.value = '';
  await loadProducerProperty();
  showToast('Dados da propriedade atualizados!', 'success');
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}
