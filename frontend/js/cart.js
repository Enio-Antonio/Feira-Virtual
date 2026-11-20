/**
 * Gerenciamento do Carrinho de Compras, Drawer Lateral e Checkout.
 */
import { apiFetch, parseError } from './api.js';
import { authState } from './auth.js';
import { closeModal, escapeHtml, formatCurrency, openModal, showToast } from './ui.js';

export const cartState = {
  items: [],
  total: 0,
};

export async function loadCart() {
  if (!authState.user || authState.user.tipo !== 'CLIENTE') {
    cartState.items = [];
    cartState.total = 0;
    renderCartBadge();
    renderCartDrawer();
    return;
  }

  try {
    const res = await apiFetch('/carrinho/');
    if (res.ok) {
      const data = await res.json();
      cartState.items = data.itens || [];
      cartState.total = parseFloat(data.total) || 0;
    }
  } catch (err) {
    console.error('Erro ao carregar carrinho:', err);
  }

  renderCartBadge();
  renderCartDrawer();
}

export function renderCartBadge() {
  const badge = document.getElementById('cartBadge');
  if (!badge) return;
  const count = cartState.items.reduce((acc, i) => acc + (parseFloat(i.quantidade) || 0), 0);
  badge.textContent = count > 0 ? String(Math.round(count)) : '0';
  badge.style.display = count > 0 ? 'inline-flex' : 'none';
}

export async function addToCart(produtoId, quantidade = 1) {
  if (!authState.user) {
    showToast('Faça login para adicionar produtos ao carrinho.', 'info');
    openModal('authModalOverlay');
    return;
  }

  if (authState.user.tipo !== 'CLIENTE') {
    showToast('Apenas contas de Cliente podem realizar compras.', 'error');
    return;
  }

  try {
    const res = await apiFetch('/carrinho/itens/', {
      method: 'POST',
      body: JSON.stringify({ produto: produtoId, quantidade }),
    });

    if (!res.ok) {
      const err = await parseError(res);
      showToast(err, 'error');
      return;
    }

    showToast('Item adicionado ao carrinho!', 'success');
    await loadCart();
    openCartDrawer();
  } catch (_) {
    showToast('Erro ao adicionar produto.', 'error');
  }
}

export async function updateItemQuantity(itemId, newQtd) {
  if (newQtd <= 0) {
    return removeItem(itemId);
  }

  try {
    const res = await apiFetch(`/carrinho/itens/${itemId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ quantidade: newQtd }),
    });

    if (!res.ok) {
      const err = await parseError(res);
      showToast(err, 'error');
      return;
    }

    await loadCart();
  } catch (_) {
    showToast('Erro ao atualizar quantidade.', 'error');
  }
}

export async function removeItem(itemId) {
  try {
    const res = await apiFetch(`/carrinho/itens/${itemId}/`, { method: 'DELETE' });
    if (!res.ok) {
      showToast('Erro ao remover item.', 'error');
      return;
    }
    await loadCart();
  } catch (_) {
    showToast('Erro ao remover item.', 'error');
  }
}

export async function clearCart() {
  try {
    const res = await apiFetch('/carrinho/', { method: 'DELETE' });
    if (!res.ok) {
      showToast('Erro ao limpar carrinho.', 'error');
      return;
    }
    showToast('Carrinho esvaziado.', 'info');
    await loadCart();
  } catch (_) {
    showToast('Erro ao limpar carrinho.', 'error');
  }
}

export function openCartDrawer() {
  const drawer = document.getElementById('cartDrawer');
  const overlay = document.getElementById('cartOverlay');
  drawer?.classList.add('open');
  drawer?.setAttribute('aria-hidden', 'false');
  overlay?.classList.add('active');
  document.getElementById('btnCloseCart')?.focus();
}

export function closeCartDrawer() {
  const drawer = document.getElementById('cartDrawer');
  const overlay = document.getElementById('cartOverlay');
  drawer?.classList.remove('open');
  drawer?.setAttribute('aria-hidden', 'true');
  overlay?.classList.remove('active');
}

export function renderCartDrawer() {
  const container = document.getElementById('cartItemsList');
  const footer = document.getElementById('cartFooter');
  const totalEl = document.getElementById('cartTotalVal');
  if (!container) return;

  if (cartState.items.length === 0) {
    container.innerHTML = `
      <div class="cart-empty">
        <span class="cart-empty__icon">🧺</span>
        <p>Seu carrinho está vazio.</p>
        <a href="#produtos" class="btn btn--outline btn--sm" id="btnContinueShopping">Explorar produtos</a>
      </div>
    `;
    if (footer) footer.style.display = 'none';
    if (totalEl) totalEl.textContent = formatCurrency(0);
    return;
  }

  if (footer) footer.style.display = 'block';
  if (totalEl) totalEl.textContent = formatCurrency(cartState.total);

  container.innerHTML = cartState.items.map(item => `
    <div class="cart-item">
      <div class="cart-item__info">
        <div class="cart-item__name">${escapeHtml(item.produto_nome)}</div>
        <div class="cart-item__price">${formatCurrency(item.preco_unitario)} / ${escapeHtml(item.unidade_medida)}</div>
        <div class="cart-item__subtotal">${formatCurrency(item.subtotal)}</div>
      </div>
      <div class="cart-item__qty">
        <button type="button" class="qty-btn btnDec" data-id="${item.id}" data-qtd="${parseFloat(item.quantidade) - 1}" aria-label="Diminuir quantidade">−</button>
        <span class="qty-val">${parseFloat(item.quantidade)}</span>
        <button type="button" class="qty-btn btnInc" data-id="${item.id}" data-qtd="${parseFloat(item.quantidade) + 1}" aria-label="Aumentar quantidade">+</button>
      </div>
      <button type="button" class="cart-item__remove btnDel" data-id="${item.id}" title="Remover item" aria-label="Remover item">🗑️</button>
    </div>
  `).join('');
}

// ── Checkout ──────────────────────────────────────────────────────────────
export async function refreshCheckoutAddresses() {
  const addrSelect = document.getElementById('enderecoSelect');
  if (!addrSelect) return;

  try {
    const res = await apiFetch('/enderecos/');
    if (res.ok) {
      const addrs = await res.json();
      if (addrs.length === 0) {
        addrSelect.innerHTML = '<option value="">Nenhum endereço cadastrado — cadastre abaixo</option>';
      } else {
        addrSelect.innerHTML = addrs.map(a => `
          <option value="${a.id}">${escapeHtml(a.rotulo)} — ${escapeHtml(a.logradouro)}, ${escapeHtml(a.numero)} (${escapeHtml(a.bairro)})</option>
        `).join('');
      }
    }
  } catch (_) {}
}

export async function openCheckout() {
  closeCartDrawer();
  const totalDisplay = document.getElementById('checkoutTotalDisplay');
  if (totalDisplay) totalDisplay.textContent = formatCurrency(cartState.total);

  await refreshCheckoutAddresses();
  openModal('checkoutModalOverlay');
}

export async function submitCheckout(payload) {
  const res = await apiFetch('/pedidos/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await parseError(res);
    throw new Error(err);
  }

  const pedidos = await res.json();
  closeModal('checkoutModalOverlay');
  await loadCart();

  showToast(
    pedidos.length > 1
      ? `${pedidos.length} pedidos criados (um por produtor)!`
      : 'Pedido realizado com sucesso!',
    'success'
  );
  window.dispatchEvent(new CustomEvent('fv:order-placed', { detail: pedidos }));

  const primeiroPix = Array.isArray(pedidos) && pedidos.find(p => p.forma_pagamento === 'PIX');
  if (primeiroPix) {
    window.dispatchEvent(new CustomEvent('fv:open-pix', { detail: primeiroPix.id }));
  }

  return pedidos;
}
