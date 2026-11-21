/**
 * Painel Administrativo de Moderação: Indicadores, Produtores, Produtos, Categorias, Pedidos, Reclamações e Usuários.
 */
import { apiFetch, parseError } from './api.js?v=20261120j';
import { statusLabels } from './orders.js?v=20261120j';
import {
  clearFormError,
  escapeHtml,
  formatCurrency,
  formatDate,
  openModal,
  renderPaginationBar,
  showFormError,
  showToast,
} from './ui.js?v=20261120j';

let adminCategoriesCache = [];

export function openAdminPanel(initialTab = 'indicadores') {
  openModal('adminPanelModalOverlay');
  switchAdminTab(initialTab);
}

export function switchAdminTab(tab) {
  const tabs = ['indicadores', 'produtores', 'produtos', 'categorias', 'pedidos', 'reclamacoes', 'usuarios'];
  tabs.forEach(t => {
    const cap = t.charAt(0).toUpperCase() + t.slice(1);
    document.querySelector(`.panel-tab[data-admin-tab="${t}"]`)?.classList.toggle('active', t === tab);
    const panel = document.getElementById(`adminTab${cap}`);
    if (panel) panel.style.display = t === tab ? 'block' : 'none';
  });

  if (tab === 'indicadores') loadAdminIndicators();
  else if (tab === 'produtores') loadAdminProducers(1);
  else if (tab === 'produtos') loadAdminProducts(1);
  else if (tab === 'categorias') loadAdminCategories();
  else if (tab === 'pedidos') loadAdminOrders(1);
  else if (tab === 'reclamacoes') loadAdminComplaints(1);
  else if (tab === 'usuarios') loadAdminUsers(1);
}

const USER_TYPE_LABELS = {
  CLIENTE: 'Clientes',
  PRODUTOR: 'Produtores',
  ENTREGADOR: 'Entregadores',
  ADMIN: 'Administradores',
};

const PRODUCER_STATUS_LABELS = {
  PENDENTE: 'Pendentes',
  APROVADO: 'Aprovados',
  SUSPENSO: 'Suspensos',
};

function renderStatsTable(title, entries, labelMap) {
  const keys = Object.keys(entries || {});
  const rows = keys.length > 0
    ? keys.map(k => `
      <tr>
        <td>${escapeHtml(labelMap[k]?.label || labelMap[k] || k)}</td>
        <td class="admin-stat-num"><strong>${Number(entries[k]) || 0}</strong></td>
      </tr>
    `).join('')
    : '<tr><td colspan="2" class="text-muted">Sem registros</td></tr>';
  return `
    <div class="admin-stat-card">
      <h4>${escapeHtml(title)}</h4>
      <table class="admin-stat-table">
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function loadAdminIndicators() {
  const el = document.getElementById('adminIndicatorsContent');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/admin/indicadores/');
    if (!res.ok) throw new Error('Acesso restrito a administradores.');
    const d = await res.json();

    el.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi-card"><span>Faturamento Total</span><strong>${formatCurrency(d.faturamento_total)}</strong></div>
        <div class="kpi-card"><span>Vendas Concluídas</span><strong>${Number(d.vendas_concluidas) || 0}</strong></div>
        <div class="kpi-card"><span>Produtos Ativos</span><strong>${Number(d.produtos_ativos) || 0}</strong></div>
        <div class="kpi-card"><span>Reclamações Abertas</span><strong>${Number(d.reclamacoes_abertas) || 0}</strong></div>
      </div>
      <div class="admin-stats-grid">
        ${renderStatsTable('Usuários por tipo', d.usuarios_por_tipo, USER_TYPE_LABELS)}
        ${renderStatsTable('Produtores por status', d.produtores_por_status, PRODUCER_STATUS_LABELS)}
        ${renderStatsTable('Pedidos por status', d.pedidos_por_status, statusLabels)}
      </div>
    `;
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminProducers(page = 1) {
  const el = document.getElementById('adminProducersList');
  const pagEl = document.getElementById('adminProducersPagination');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';
  if (pagEl) pagEl.innerHTML = '';

  try {
    const res = await apiFetch(`/admin/produtores/?page=${page}`);
    const data = await res.json();
    const list = data.results || data || [];
    el.innerHTML = list.map(p => `
      <div class="panel-list-item">
        <div class="panel-list-item__info">
          <strong>${escapeHtml(p.nome_propriedade)}</strong>
          <span>${escapeHtml(p.cidade || '')}/${escapeHtml(p.estado || '')} • <span class="badge badge--outline">${escapeHtml(p.status)}</span></span>
        </div>
        <div class="panel-list-item__actions">
          ${p.status !== 'APROVADO' ? `<button type="button" class="btn btn--primary btn--sm btnAdminAction" data-resource="produtores" data-id="${p.id}" data-action="aprovar">Aprovar</button>` : ''}
          ${p.status !== 'SUSPENSO' ? `<button type="button" class="btn btn--outline btn--sm text-danger btnAdminAction" data-resource="produtores" data-id="${p.id}" data-action="suspender">Suspender</button>` : ''}
        </div>
      </div>
    `).join('');
    renderPaginationBar(pagEl, data, page, (p) => loadAdminProducers(p));
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminProducts(page = 1) {
  const el = document.getElementById('adminProductsList');
  const pagEl = document.getElementById('adminProductsPagination');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';
  if (pagEl) pagEl.innerHTML = '';

  try {
    const res = await apiFetch(`/admin/produtos/?page=${page}`);
    const data = await res.json();
    const list = data.results || data || [];
    el.innerHTML = list.map(p => `
      <div class="panel-list-item">
        <div class="panel-list-item__info">
          <strong>${escapeHtml(p.nome)}</strong>
          <span>${formatCurrency(p.preco)} • <span class="badge ${p.ativo ? 'badge--success' : 'badge--outline'}">${p.ativo ? 'Visível' : 'Oculto'}</span></span>
        </div>
        <div class="panel-list-item__actions">
          ${p.ativo
            ? `<button type="button" class="btn btn--outline btn--sm text-danger btnAdminAction" data-resource="produtos" data-id="${p.id}" data-action="ocultar">Ocultar</button>`
            : `<button type="button" class="btn btn--primary btn--sm btnAdminAction" data-resource="produtos" data-id="${p.id}" data-action="reexibir">Reexibir</button>`}
        </div>
      </div>
    `).join('');
    renderPaginationBar(pagEl, data, page, (p) => loadAdminProducts(p));
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

// ── Categorias (CRUD Admin) ───────────────────────────────────────────────
export async function loadAdminCategories() {
  const el = document.getElementById('adminCategoriesList');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/categorias/');
    if (!res.ok) throw new Error('Falha ao carregar categorias.');
    const data = await res.json();
    adminCategoriesCache = data.results || data || [];

    if (adminCategoriesCache.length === 0) {
      el.innerHTML = '<div class="empty-state"><p>Nenhuma categoria cadastrada.</p></div>';
      return;
    }

    el.innerHTML = adminCategoriesCache.map(c => `
      <div class="panel-list-item">
        <div class="panel-list-item__info">
          <strong>${escapeHtml(c.nome)}</strong>
          <span>${escapeHtml(c.descricao || 'Sem descrição')} • <span class="badge ${c.ativa ? 'badge--success' : 'badge--outline'}">${c.ativa ? 'Ativa' : 'Inativa'}</span></span>
        </div>
        <div class="panel-list-item__actions">
          <button type="button" class="btn btn--outline btn--sm btnEditAdminCat" data-id="${c.id}">Editar</button>
          <button type="button" class="btn btn--outline btn--sm btnToggleAdminCat" data-id="${c.id}" data-ativa="${c.ativa ? '0' : '1'}">${c.ativa ? 'Desativar' : 'Ativar'}</button>
          <button type="button" class="btn btn--outline btn--sm text-danger btnDeleteAdminCat" data-id="${c.id}">Excluir</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export function openAdminCategoryForm(catId = null) {
  const wrap = document.getElementById('adminCategoryFormWrap');
  const form = document.getElementById('adminCategoryForm');
  if (!wrap || !form) return;
  clearFormError('adminCategoryError');
  form.reset();

  if (catId) {
    const c = adminCategoriesCache.find(x => String(x.id) === String(catId));
    if (c) {
      document.getElementById('adminCatId').value = String(c.id);
      document.getElementById('adminCatNome').value = c.nome || '';
      document.getElementById('adminCatDesc').value = c.descricao || '';
      document.getElementById('adminCatAtiva').checked = Boolean(c.ativa);
    }
  } else {
    document.getElementById('adminCatId').value = '';
    document.getElementById('adminCatAtiva').checked = true;
  }
  wrap.style.display = 'block';
}

export async function saveAdminCategory() {
  clearFormError('adminCategoryError');
  const id = document.getElementById('adminCatId').value;
  const payload = {
    nome: document.getElementById('adminCatNome').value.trim(),
    descricao: document.getElementById('adminCatDesc').value.trim(),
    ativa: document.getElementById('adminCatAtiva').checked,
  };
  const endpoint = id ? `/categorias/${id}/` : '/categorias/';
  const method = id ? 'PATCH' : 'POST';

  const res = await apiFetch(endpoint, { method, body: JSON.stringify(payload) });
  if (!res.ok) {
    showFormError('adminCategoryError', await parseError(res));
    return;
  }
  document.getElementById('adminCategoryFormWrap').style.display = 'none';
  showToast(id ? 'Categoria atualizada!' : 'Categoria criada!', 'success');
  await loadAdminCategories();
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}

export async function toggleAdminCategory(id, ativa) {
  const res = await apiFetch(`/categorias/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify({ ativa }),
  });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast(ativa ? 'Categoria ativada.' : 'Categoria desativada.', 'success');
  await loadAdminCategories();
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}

export async function deleteAdminCategory(id) {
  if (!confirm('Deseja realmente excluir esta categoria?')) return;
  const res = await apiFetch(`/categorias/${id}/`, { method: 'DELETE' });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Categoria excluída.', 'info');
  await loadAdminCategories();
  window.dispatchEvent(new CustomEvent('fv:catalog-updated'));
}

// ── Pedidos (Listagem Admin com Filtro por Status e Paginação) ────────────
export async function loadAdminOrders(page = 1) {
  const el = document.getElementById('adminOrdersList');
  const pagEl = document.getElementById('adminOrdersPagination');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';
  if (pagEl) pagEl.innerHTML = '';

  const statusFilter = document.getElementById('adminOrderStatusFilter')?.value || '';
  const params = new URLSearchParams({ page: String(page) });
  if (statusFilter) params.set('status', statusFilter);

  try {
    const res = await apiFetch(`/admin/pedidos/?${params.toString()}`);
    if (!res.ok) throw new Error('Falha ao carregar pedidos.');
    const data = await res.json();
    const list = data.results || data || [];

    if (list.length === 0) {
      el.innerHTML = '<div class="empty-state"><p>Nenhum pedido encontrado para o filtro selecionado.</p></div>';
      return;
    }

    el.innerHTML = list.map(o => {
      const st = statusLabels[o.status] || { label: o.status, class: '' };
      return `
        <div class="panel-list-item">
          <div class="panel-list-item__info">
            <strong>${escapeHtml(o.numero_publico || `#${o.id}`)} • ${formatCurrency(o.total_com_frete || o.total)}</strong>
            <span>Produtor: <strong>${escapeHtml(o.produtor_nome || '-')}</strong> • Cliente: ${escapeHtml(o.cliente_nome || '-')}</span>
            <span class="text-muted">${formatDate(o.criado_em)} • ${escapeHtml(o.modalidade)} • ${escapeHtml(o.forma_pagamento)}</span>
          </div>
          <div class="panel-list-item__actions">
            <span class="badge ${st.class}">${escapeHtml(st.label)}</span>
          </div>
        </div>
      `;
    }).join('');
    renderPaginationBar(pagEl, data, page, (p) => loadAdminOrders(p));
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminComplaints(page = 1) {
  const el = document.getElementById('adminComplaintsList');
  const pagEl = document.getElementById('adminComplaintsPagination');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';
  if (pagEl) pagEl.innerHTML = '';

  try {
    const res = await apiFetch(`/admin/reclamacoes/?page=${page}`);
    const data = await res.json();
    const list = data.results || data || [];
    if (list.length === 0) {
      el.innerHTML = '<div class="empty-state"><p>Nenhuma reclamação cadastrada.</p></div>';
      return;
    }

    el.innerHTML = list.map(r => `
      <div class="order-card" data-complaint-id="${r.id}">
        <div class="order-card__header">
          <strong>#${r.id} — ${escapeHtml(r.assunto)}</strong>
          <span class="badge badge--outline">Pedido #${r.pedido}</span>
        </div>
        <p>${escapeHtml(r.descricao)}</p>
        <div class="form-group" style="margin-top: 8px;">
          <select class="form-select adminComplaintStatus" data-id="${r.id}">
            <option value="ABERTA" ${r.status === 'ABERTA' ? 'selected' : ''}>Aberta</option>
            <option value="EM_ANALISE" ${r.status === 'EM_ANALISE' ? 'selected' : ''}>Em análise</option>
            <option value="RESOLVIDA" ${r.status === 'RESOLVIDA' ? 'selected' : ''}>Resolvida</option>
          </select>
        </div>
        <div class="form-group">
          <textarea class="form-input adminComplaintReply" data-id="${r.id}" rows="2" placeholder="Resposta da moderação...">${escapeHtml(r.resposta_admin || '')}</textarea>
        </div>
        <button type="button" class="btn btn--primary btn--sm btnSaveComplaint" data-id="${r.id}">Salvar Moderação</button>
      </div>
    `).join('');
    renderPaginationBar(pagEl, data, page, (p) => loadAdminComplaints(p));
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminUsers(page = 1) {
  const el = document.getElementById('adminUsersList');
  const pagEl = document.getElementById('adminUsersPagination');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';
  if (pagEl) pagEl.innerHTML = '';

  try {
    const res = await apiFetch(`/admin/usuarios/?page=${page}`);
    const data = await res.json();
    const list = data.results || data || [];
    el.innerHTML = list.map(u => `
      <div class="panel-list-item">
        <div class="panel-list-item__info">
          <strong>${escapeHtml(u.username)} (${escapeHtml(u.tipo)})</strong>
          <span>${escapeHtml(u.email)} • <span class="badge ${u.is_active ? 'badge--success' : 'badge--outline'}">${u.is_active ? 'Ativo' : 'Bloqueado'}</span></span>
        </div>
        <div class="panel-list-item__actions">
          ${u.is_active
            ? `<button type="button" class="btn btn--outline btn--sm text-danger btnAdminAction" data-resource="usuarios" data-id="${u.id}" data-action="bloquear">Bloquear</button>`
            : `<button type="button" class="btn btn--primary btn--sm btnAdminAction" data-resource="usuarios" data-id="${u.id}" data-action="reativar">Reativar</button>`}
        </div>
      </div>
    `).join('');
    renderPaginationBar(pagEl, data, page, (p) => loadAdminUsers(p));
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export async function handleAdminAction(resource, id, action) {
  const res = await apiFetch(`/admin/${resource}/${id}/${action}/`, { method: 'POST' });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Ação administrativa aplicada!', 'success');
  switchAdminTab(resource);
}

export async function saveAdminComplaint(id) {
  const statusEl = document.querySelector(`.adminComplaintStatus[data-id="${id}"]`);
  const replyEl = document.querySelector(`.adminComplaintReply[data-id="${id}"]`);
  const res = await apiFetch(`/admin/reclamacoes/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify({
      status: statusEl?.value,
      resposta_admin: replyEl?.value.trim() || '',
    }),
  });
  if (!res.ok) {
    showToast(await parseError(res), 'error');
    return;
  }
  showToast('Reclamação atualizada!', 'success');
}
