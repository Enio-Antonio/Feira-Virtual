/**
 * Painel Administrativo de Moderação: Indicadores, Produtores, Produtos, Reclamações e Usuários.
 */
import { apiFetch, parseError } from './api.js';
import { escapeHtml, formatCurrency, openModal, showToast } from './ui.js';

export function openAdminPanel(initialTab = 'indicadores') {
  openModal('adminPanelModalOverlay');
  switchAdminTab(initialTab);
}

export function switchAdminTab(tab) {
  const tabs = ['indicadores', 'produtores', 'produtos', 'reclamacoes', 'usuarios'];
  tabs.forEach(t => {
    const cap = t.charAt(0).toUpperCase() + t.slice(1);
    document.querySelector(`.panel-tab[data-admin-tab="${t}"]`)?.classList.toggle('active', t === tab);
    const panel = document.getElementById(`adminTab${cap}`);
    if (panel) panel.style.display = t === tab ? 'block' : 'none';
  });

  if (tab === 'indicadores') loadAdminIndicators();
  else if (tab === 'produtores') loadAdminProducers();
  else if (tab === 'produtos') loadAdminProducts();
  else if (tab === 'reclamacoes') loadAdminComplaints();
  else if (tab === 'usuarios') loadAdminUsers();
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
      <div class="demo-box" style="margin-top: var(--space-4);">
        <p><strong>Usuários:</strong> ${escapeHtml(JSON.stringify(d.usuarios_por_tipo || {}))}</p>
        <p><strong>Produtores:</strong> ${escapeHtml(JSON.stringify(d.produtores_por_status || {}))}</p>
        <p><strong>Pedidos:</strong> ${escapeHtml(JSON.stringify(d.pedidos_por_status || {}))}</p>
      </div>
    `;
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminProducers() {
  const el = document.getElementById('adminProducersList');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/admin/produtores/');
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
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminProducts() {
  const el = document.getElementById('adminProductsList');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/admin/produtos/');
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
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminComplaints() {
  const el = document.getElementById('adminComplaintsList');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/admin/reclamacoes/');
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
  } catch (err) {
    el.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAdminUsers() {
  const el = document.getElementById('adminUsersList');
  if (!el) return;
  el.innerHTML = '<div class="catalog-loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch('/admin/usuarios/');
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
