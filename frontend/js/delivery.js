/**
 * Painel do Entregador: Entregas Disponíveis, Minhas Entregas e Dados do Veículo.
 */
import { apiFetch, parseError } from './api.js';
import { statusLabels } from './orders.js';
import { clearFormError, escapeHtml, formatCurrency, openModal, showFormError, showToast } from './ui.js';

export function openDeliveryPanel(initialTab = 'disponiveis') {
  openModal('deliveryPanelModalOverlay');
  switchDeliveryTab(initialTab);
}

export function switchDeliveryTab(tab) {
  const map = {
    disponiveis: 'deliveryTabDisponiveis',
    minhas: 'deliveryTabMinhas',
    veiculo: 'deliveryTabVeiculo',
  };
  Object.entries(map).forEach(([k, id]) => {
    document.querySelector(`.panel-tab[data-delivery-tab="${k}"]`)?.classList.toggle('active', k === tab);
    const el = document.getElementById(id);
    if (el) el.style.display = k === tab ? 'block' : 'none';
  });

  if (tab === 'disponiveis') loadDeliveries('disponiveis', 'deliveryAvailableList');
  else if (tab === 'minhas') loadDeliveries('minhas', 'deliveryMineList');
  else if (tab === 'veiculo') loadDeliveryVehicle();
}

async function loadDeliveries(escopo, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch(`/entregas/?escopo=${escopo}`);
    if (!res.ok) throw new Error('Erro ao carregar entregas.');
    const data = await res.json();
    const list = data.results || data || [];

    if (list.length === 0) {
      el.innerHTML = `<div class="empty-state"><p>${escopo === 'disponiveis' ? 'Nenhuma entrega disponível no momento.' : 'Você ainda não assumiu nenhuma entrega.'}</p></div>`;
      return;
    }

    el.innerHTML = list.map(o => {
      const st = statusLabels[o.status] || { label: o.status, class: '' };
      let btn = '';
      if (escopo === 'disponiveis') {
        btn = `<button type="button" class="btn btn--primary btn--sm btnDeliveryAction" data-id="${o.id}" data-action="aceitar">🛵 Aceitar Entrega</button>`;
      } else if (['ACEITO', 'EM_PREPARO', 'PRONTO'].includes(o.status)) {
        btn = `<button type="button" class="btn btn--primary btn--sm btnDeliveryAction" data-id="${o.id}" data-action="saiu-para-entrega">🚚 Saiu para Entrega</button>`;
      } else if (o.status === 'EM_ENTREGA') {
        btn = `<button type="button" class="btn btn--cta btn--sm btnDeliveryAction" data-id="${o.id}" data-action="confirmar">✅ Confirmar Entrega</button>`;
      }

      return `
        <div class="order-card">
          <div class="order-card__header">
            <strong>${escapeHtml(o.numero_publico || `#${o.id}`)} — ${escapeHtml(o.produtor_nome)}</strong>
            <span class="badge ${st.class}">${escapeHtml(st.label)}</span>
          </div>
          <div class="order-card__body">
            <p><strong>Cliente:</strong> ${escapeHtml(o.cliente_nome || 'Cliente')}</p>
            <p><strong>Endereço:</strong> ${escapeHtml(o.endereco_entrega || 'Não informado')}</p>
          </div>
          <div class="order-card__footer">
            <strong>${formatCurrency(o.total_com_frete || o.total)}</strong>
            <div>${btn}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export async function handleDeliveryAction(orderId, action) {
  const res = await apiFetch(`/entregas/${orderId}/${action}/`, { method: 'POST' });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Entrega atualizada com sucesso!', 'success');
  loadDeliveries('disponiveis', 'deliveryAvailableList');
  loadDeliveries('minhas', 'deliveryMineList');
}

async function loadDeliveryVehicle() {
  try {
    const res = await apiFetch('/perfil/entregador/');
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('delivVeiculo').value = d.veiculo || '';
    document.getElementById('delivPlaca').value = d.placa || '';
    document.getElementById('delivArea').value = d.area_atuacao || '';
  } catch (_) {}
}

export async function saveDeliveryVehicle() {
  clearFormError('deliveryVehicleError');
  const payload = {
    veiculo: document.getElementById('delivVeiculo').value.trim(),
    placa: document.getElementById('delivPlaca').value.trim().toUpperCase(),
    area_atuacao: document.getElementById('delivArea').value.trim(),
  };
  const res = await apiFetch('/perfil/entregador/', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    showFormError('deliveryVehicleError', await parseError(res));
    return;
  }
  showToast('Dados do veículo salvos!', 'success');
}
