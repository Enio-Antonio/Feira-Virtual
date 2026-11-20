/**
 * Pedidos do Cliente (Timeline, Cancelamento, Pix QR/Copia-e-Cola), Avaliações, Reclamações e Endereços (ViaCEP).
 */
import { apiFetch, parseError } from './api.js';
import { closeModal, escapeHtml, formatCurrency, formatDate, generateSimpleQrSvg, openModal, showToast } from './ui.js';

const ordersCache = new Map();

export const statusLabels = {
  PENDENTE: { label: 'Aguardando produtor', class: 'status--pending' },
  ACEITO: { label: 'Aceito pelo produtor', class: 'status--accepted' },
  RECUSADO: { label: 'Recusado', class: 'status--refused' },
  EM_PREPARO: { label: 'Em colheita/preparo', class: 'status--preparing' },
  PRONTO: { label: 'Pronto (entrega/retirada)', class: 'status--ready' },
  EM_ENTREGA: { label: 'Saiu para entrega', class: 'status--delivering' },
  CONCLUIDO: { label: 'Concluído', class: 'status--completed' },
  CANCELADO: { label: 'Cancelado', class: 'status--cancelled' },
};

export async function loadMyOrders() {
  const container = document.getElementById('myOrdersList');
  if (!container) return;

  container.innerHTML = '<div class="catalog-loading"><div class="spinner"></div><p>Carregando seus pedidos...</p></div>';
  switchOrdersTab('pedidos');
  openModal('myOrdersModalOverlay');

  try {
    const res = await apiFetch('/pedidos/');
    if (!res.ok) throw new Error('Falha ao obter pedidos.');
    const data = await res.json();
    const orders = data.results || data || [];

    ordersCache.clear();
    orders.forEach(o => ordersCache.set(String(o.id), o));

    if (orders.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <p class="empty-state__icon">📦</p>
          <p>Você ainda não realizou nenhum pedido.</p>
        </div>
      `;
      return;
    }

    renderOrdersList(container, orders);
  } catch (err) {
    container.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export function switchOrdersTab(tab) {
  const tabPedidos = document.getElementById('tabOrdersList');
  const tabReclam = document.getElementById('tabMyComplaints');
  const listPedidos = document.getElementById('myOrdersList');
  const listReclam = document.getElementById('myComplaintsList');

  if (tab === 'pedidos') {
    tabPedidos?.classList.add('active');
    tabReclam?.classList.remove('active');
    if (listPedidos) listPedidos.style.display = 'flex';
    if (listReclam) listReclam.style.display = 'none';
  } else {
    tabReclam?.classList.add('active');
    tabPedidos?.classList.remove('active');
    if (listReclam) listReclam.style.display = 'flex';
    if (listPedidos) listPedidos.style.display = 'none';
    loadMyComplaints();
  }
}

function renderOrdersList(container, orders) {
  container.innerHTML = orders.map(o => {
    const st = statusLabels[o.status] || { label: o.status, class: '' };
    const canCancel = ['PENDENTE', 'ACEITO'].includes(o.status);
    const isCompleted = o.status === 'CONCLUIDO';
    const isPix = o.forma_pagamento === 'PIX' && !['CANCELADO', 'RECUSADO'].includes(o.status);

    const timelineHtml = (o.historico || []).length > 0
      ? `
        <div class="order-timeline">
          ${o.historico.map(h => {
            const hst = statusLabels[h.status] || { label: h.status };
            return `<span class="timeline-step"><strong>${escapeHtml(hst.label)}</strong> <small>${formatDate(h.criado_em)}</small></span>`;
          }).join('')}
        </div>
      `
      : '';

    return `
      <div class="order-card" data-id="${o.id}">
        <div class="order-card__header">
          <div>
            <strong>Pedido ${escapeHtml(o.numero_publico || `#${o.id}`)}</strong>
            <span class="text-muted">• ${formatDate(o.criado_em)}</span>
          </div>
          <span class="badge ${st.class}">${escapeHtml(st.label)}</span>
        </div>

        <div class="order-card__body">
          <p><strong>Produtor:</strong> 🏡 ${escapeHtml(o.produtor_nome)}</p>
          <p><strong>Modalidade:</strong> ${o.modalidade === 'ENTREGA' ? '🚚 Entrega' : '🏪 Retirada'} • <strong>Pagamento:</strong> ${escapeHtml(o.forma_pagamento)}</p>
          ${o.endereco_entrega ? `<p><strong>Endereço:</strong> ${escapeHtml(o.endereco_entrega)}</p>` : ''}
          ${o.previsao_entrega ? `<p><strong>Previsão:</strong> 🕒 ${escapeHtml(o.previsao_entrega)}</p>` : ''}
          ${o.motivo_cancelamento ? `<p class="text-danger"><strong>Motivo:</strong> ${escapeHtml(o.motivo_cancelamento)}</p>` : ''}

          <ul class="order-items-list">
            ${(o.itens || []).map(it => `
              <li>${escapeHtml(it.nome_produto)} (${parseFloat(it.quantidade)} ${escapeHtml(it.unidade_medida)}) — ${formatCurrency(it.subtotal)}</li>
            `).join('')}
          </ul>

          ${timelineHtml}
        </div>

        <div class="order-card__footer">
          <div class="order-card__total">
            Total: <strong>${formatCurrency(o.total_com_frete || o.total)}</strong>
          </div>
          <div class="order-card__actions">
            ${isPix ? `
              <button type="button" class="btn btn--primary btn--sm btnShowPix" data-id="${o.id}">
                📱 Ver Pix / QR Code
              </button>
            ` : ''}
            ${canCancel ? `
              <button type="button" class="btn btn--outline btn--sm text-danger btnCancelOrder" data-id="${o.id}">
                Cancelar
              </button>
            ` : ''}
            ${isCompleted ? `
              <button type="button" class="btn btn--outline btn--sm btnOpenReview" data-id="${o.id}">
                ⭐ Avaliar
              </button>
            ` : ''}
            <button type="button" class="btn btn--outline btn--sm btnOpenComplaint" data-id="${o.id}">
              ⚠️ Reclamação
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

export async function loadMyComplaints() {
  const container = document.getElementById('myComplaintsList');
  if (!container) return;
  container.innerHTML = '<div class="catalog-loading"><div class="spinner"></div><p>Carregando reclamações...</p></div>';

  try {
    const res = await apiFetch('/reclamacoes/');
    if (!res.ok) throw new Error('Falha ao carregar reclamações.');
    const data = await res.json();
    const list = data.results || data || [];
    if (list.length === 0) {
      container.innerHTML = '<div class="empty-state"><p>Você não possui reclamações registradas.</p></div>';
      return;
    }

    container.innerHTML = list.map(r => `
      <div class="order-card">
        <div class="order-card__header">
          <strong>${escapeHtml(r.assunto)}</strong>
          <span class="badge badge--outline">${escapeHtml(r.status)}</span>
        </div>
        <p>${escapeHtml(r.descricao)}</p>
        ${r.resposta_admin ? `<div class="demo-box" style="margin-top: 8px; margin-bottom: 0;"><strong>Resposta da moderação:</strong> ${escapeHtml(r.resposta_admin)}</div>` : ''}
        <span class="text-muted">${formatDate(r.criado_em)}</span>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

// ── Pagamento Pix (Modal + QR SVG + Copia-e-Cola) ──────────────────────────
export async function showPixDetails(pedidoId) {
  try {
    const res = await apiFetch(`/pedidos/${pedidoId}/pix/`);
    if (!res.ok) {
      const err = await parseError(res);
      showToast(err, 'error');
      return;
    }

    const pix = await res.json();
    document.getElementById('pixValorDisplay').textContent = formatCurrency(pix.valor);
    document.getElementById('pixChaveDisplay').textContent = pix.chave || 'Chave não configurada';
    document.getElementById('pixCopiaColaInput').value = pix.copia_e_cola || '';

    const qrBox = document.getElementById('pixQrContainer');
    if (qrBox) {
      qrBox.innerHTML = generateSimpleQrSvg(pix.copia_e_cola || pix.chave || String(pedidoId));
    }

    openModal('pixModalOverlay');
  } catch (_) {
    showToast('Erro ao consultar pagamento Pix.', 'error');
  }
}

export async function cancelOrder(pedidoId) {
  const motivo = prompt('Informe o motivo do cancelamento (opcional):');
  if (motivo === null) return;
  try {
    const res = await apiFetch(`/pedidos/${pedidoId}/cancelar/`, {
      method: 'POST',
      body: JSON.stringify({ motivo }),
    });
    if (!res.ok) {
      const err = await parseError(res);
      showToast(err, 'error');
      return;
    }
    showToast('Pedido cancelado com sucesso.', 'info');
    await loadMyOrders();
  } catch (_) {
    showToast('Erro ao cancelar pedido.', 'error');
  }
}

// ── Avaliações e Reclamações ──────────────────────────────────────────────
export function openReviewModalForOrder(pedidoId) {
  const pedido = ordersCache.get(String(pedidoId));
  const select = document.getElementById('reviewTarget');
  if (!select || !pedido) return;

  const opts = [];
  if (pedido.produtor) {
    opts.push(`<option value="produtor:${pedido.produtor}">🏡 Produtor: ${escapeHtml(pedido.produtor_nome)}</option>`);
  }
  (pedido.itens || []).forEach(it => {
    if (it.produto) {
      opts.push(`<option value="produto:${it.produto}">🥬 Produto: ${escapeHtml(it.nome_produto)}</option>`);
    }
  });
  select.innerHTML = opts.join('');
  document.getElementById('reviewOrderId').value = String(pedidoId);
  document.getElementById('reviewComment').value = '';
  openModal('reviewModalOverlay');
}

export function openComplaintModalForOrder(pedidoId) {
  const pedido = ordersCache.get(String(pedidoId));
  document.getElementById('complaintOrderId').value = String(pedidoId);
  const label = document.getElementById('complaintOrderLabel');
  if (label) {
    label.textContent = pedido
      ? `Pedido ${pedido.numero_publico} — ${pedido.produtor_nome}`
      : `Pedido #${pedidoId}`;
  }
  document.getElementById('complaintSubject').value = '';
  document.getElementById('complaintDescription').value = '';
  openModal('complaintModalOverlay');
}

export async function submitReview(payload) {
  const res = await apiFetch('/avaliacoes/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await parseError(res);
    throw new Error(err);
  }
  showToast('Avaliação enviada com sucesso! Obrigado pelo feedback.', 'success');
  closeModal('reviewModalOverlay');
}

export async function submitComplaint(payload) {
  const res = await apiFetch('/reclamacoes/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await parseError(res);
    throw new Error(err);
  }
  showToast('Reclamação registrada. Nossa moderação analisará o caso.', 'info');
  closeModal('complaintModalOverlay');
}

// ── Gerenciador de Endereços com ViaCEP ───────────────────────────────────
export async function loadAddresses() {
  const list = document.getElementById('addressesList');
  if (!list) return;

  try {
    const res = await apiFetch('/enderecos/');
    if (!res.ok) return;
    const addrs = await res.json();

    if (addrs.length === 0) {
      list.innerHTML = '<p class="text-muted">Nenhum endereço cadastrado ainda.</p>';
      return;
    }

    list.innerHTML = addrs.map(a => `
      <div class="address-item">
        <div>
          <strong>${escapeHtml(a.rotulo)}</strong>
          <p>${escapeHtml(a.logradouro)}, ${escapeHtml(a.numero)}${a.complemento ? ` (${escapeHtml(a.complemento)})` : ''}</p>
          <span class="text-muted">${escapeHtml(a.bairro)}, ${escapeHtml(a.cidade)}/${escapeHtml(a.estado)} — CEP ${escapeHtml(a.cep)}</span>
        </div>
        <button type="button" class="btn btn--outline btn--sm text-danger btnDeleteAddress" data-id="${a.id}">Excluir</button>
      </div>
    `).join('');
  } catch (_) {}
}

export async function createAddress(payload) {
  const res = await apiFetch('/enderecos/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await parseError(res);
    throw new Error(err);
  }
  showToast('Endereço cadastrado com sucesso!', 'success');
  await loadAddresses();
  window.dispatchEvent(new CustomEvent('fv:addresses-updated'));
}

export async function deleteAddress(id) {
  const res = await apiFetch(`/enderecos/${id}/`, { method: 'DELETE' });
  if (!res.ok) {
    showToast('Erro ao remover endereço.', 'error');
    return;
  }
  showToast('Endereço removido.', 'info');
  await loadAddresses();
  window.dispatchEvent(new CustomEvent('fv:addresses-updated'));
}

export async function fetchViaCEP(cepClean) {
  try {
    const res = await fetch(`https://viacep.com.br/ws/${cepClean}/json/`);
    if (!res.ok) return null;
    const data = await res.json();
    if (data.erro) return null;
    return data;
  } catch (_) {
    return null;
  }
}
