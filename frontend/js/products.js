/**
 * Catálogo de Produtos, Filtros, Busca, Paginação, Detalhes, Vitrine de Produtores e Estatísticas.
 */
import { apiFetch } from './api.js';
import { addToCart } from './cart.js';
import { escapeHtml, formatCurrency, formatDate, getUnitStep, openModal, renderProductSkeletons, safeUrl } from './ui.js';

export const catalogState = {
  categories: [],
  selectedCategory: '',
  searchQuery: '',
  selectedProductionType: '',
  ordering: 'nome',
  selectedProducer: null,
  selectedProducerName: '',
  currentPage: 1,
  totalPages: 1,
  totalCount: 0,
};

export async function loadCategories() {
  const container = document.getElementById('categoryPills');
  if (!container) return;

  try {
    const res = await apiFetch('/categorias/');
    if (res.ok) {
      const data = await res.json();
      catalogState.categories = data.results || data || [];
      renderCategoryPills();
    }
  } catch (err) {
    console.error('Erro ao carregar categorias:', err);
  }
}

export function renderCategoryPills() {
  const container = document.getElementById('categoryPills');
  if (!container) return;

  const allPill = `
    <button type="button" class="pill ${!catalogState.selectedCategory ? 'active' : ''}" data-category="" role="tab" aria-selected="${!catalogState.selectedCategory}">
      🌱 Todas as categorias
    </button>
  `;

  const pills = catalogState.categories
    .filter(c => c.ativa !== false)
    .map(c => {
      const active = catalogState.selectedCategory === String(c.id);
      return `
        <button type="button" class="pill ${active ? 'active' : ''}" data-category="${c.id}" role="tab" aria-selected="${active}">
          ${escapeHtml(c.nome)}
        </button>
      `;
    })
    .join('');

  container.innerHTML = allPill + pills;
}

function renderActiveProducerFilter() {
  const wrap = document.getElementById('activeProducerFilter');
  if (!wrap) return;
  if (!catalogState.selectedProducer) {
    wrap.innerHTML = '';
    return;
  }
  wrap.innerHTML = `
    <div class="active-filter-chip">
      <span>Filtrando produtor: <strong>${escapeHtml(catalogState.selectedProducerName)}</strong></span>
      <button type="button" class="btn-clear-chip" id="btnClearProducerFilter" aria-label="Remover filtro de produtor">✕</button>
    </div>
  `;
}

export async function loadProducts(page = 1) {
  const grid = document.getElementById('productsGrid');
  if (!grid) return;

  catalogState.currentPage = page;
  renderActiveProducerFilter();
  renderProductSkeletons(grid, 6);

  const params = new URLSearchParams({ page: String(page) });
  if (catalogState.selectedCategory) params.set('categoria', catalogState.selectedCategory);
  if (catalogState.searchQuery) params.set('search', catalogState.searchQuery);
  if (catalogState.selectedProductionType) params.set('tipo_producao', catalogState.selectedProductionType);
  if (catalogState.selectedProducer) params.set('produtor', String(catalogState.selectedProducer));
  if (catalogState.ordering) params.set('ordering', catalogState.ordering);

  try {
    const res = await apiFetch(`/produtos/?${params.toString()}`);
    if (!res.ok) throw new Error('Falha ao carregar catálogo');

    const data = await res.json();
    const products = data.results || data || [];
    catalogState.totalCount = data.count ?? products.length;
    catalogState.totalPages = Math.ceil(catalogState.totalCount / 20) || 1;

    renderProductsGrid(products);
    updateHeroProductRating(products);
    renderPagination();
  } catch (_) {
    grid.innerHTML = `
      <div class="catalog-empty">
        <p style="font-size: 2.5rem; margin-bottom: 8px;">⚠️</p>
        <p>Não foi possível carregar os produtos no momento.</p>
      </div>
    `;
  }
}

const typeBadges = {
  ORGANICO_CERTIFICADO: '<span class="badge badge--cultivo badge--cultivo-organico">Orgânico</span>',
  AGROECOLOGICO: '<span class="badge badge--cultivo badge--cultivo-agro">Agroecológico</span>',
  CONVENCIONAL: '<span class="badge badge--cultivo badge--cultivo-conv">Convencional</span>',
};

const PIX_BADGE_HTML =
  '<span class="payment-badge"><img src="/static/assets/pix-icon.webp" alt="" class="pix-brand-icon" width="16" height="16" /> Pix</span>';

function renderProducerAvatarImg(p) {
  const customUrl = p?.foto_propriedade ? safeUrl(p.foto_propriedade, '') : '';
  const nome = escapeHtml(p?.nome_propriedade || 'Propriedade Rural');
  if (customUrl) {
    return `<img src="${escapeHtml(customUrl)}" alt="Propriedade ${nome}" class="producer-card__img" loading="lazy" />`;
  }
  return `<img src="/static/assets/logo-icon.webp" alt="Logo Feira Virtual — ${nome}" class="producer-card__img producer-card__img--default" loading="lazy" />`;
}

function hasValidRating(p) {
  if (!p) return false;
  const total = Number(p.total_avaliacoes) || 0;
  const media = p.nota_media !== null && p.nota_media !== undefined ? Number(p.nota_media) : NaN;
  return total > 0 && Number.isFinite(media) && media > 0;
}

function updateHeroProductRating(products) {
  const header = document.getElementById('heroProductHeader');
  if (!header) return;

  const existingBadge = header.querySelector('.product-card-hero__badge');
  if (existingBadge) existingBadge.remove();

  if (!Array.isArray(products) || products.length === 0) return;
  const heroProd =
    products.find(p => String(p.nome || '').toLowerCase().includes('alface')) || products[0];

  if (hasValidRating(heroProd)) {
    const badge = document.createElement('div');
    badge.className = 'product-card-hero__badge';
    const span = document.createElement('span');
    span.textContent = `⭐ ${Number(heroProd.nota_media).toFixed(1)}`;
    badge.appendChild(span);
    header.appendChild(badge);
  }
}

function renderProductsGrid(products) {
  const grid = document.getElementById('productsGrid');
  if (!grid) return;

  if (products.length === 0) {
    grid.innerHTML = `
      <div class="catalog-empty">
        <p style="font-size: 3rem; margin-bottom: 8px;">🔍</p>
        <p>Nenhum produto encontrado com os filtros selecionados.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = products.map(p => {
    const semEstoque = parseFloat(p.estoque) <= 0;
    const produtorNome = p.produtor_nome || 'Produtor Parceiro';
    const customImgUrl = p.imagem ? safeUrl(p.imagem, '') : '';
    const imgUrl = customImgUrl || '/static/assets/logo-icon.webp';
    const imgClass = customImgUrl ? 'product-card__img' : 'product-card__img product-card__img--default';
    const nota = hasValidRating(p) ? `⭐ ${Number(p.nota_media).toFixed(1)}` : '';

    return `
      <article class="product-card ${semEstoque ? 'card--out-of-stock' : ''}">
        <div class="product-card__thumb btnProductDetail" data-id="${p.id}" role="button" tabindex="0" aria-label="Ver detalhes de ${escapeHtml(p.nome)}">
          <img src="${escapeHtml(imgUrl)}" alt="${escapeHtml(p.nome)}" class="${imgClass}" loading="lazy" />
          <div class="product-card__badges">
            ${typeBadges[p.tipo_producao] || ''}
            ${nota ? `<span class="badge badge--outline">${nota}</span>` : ''}
          </div>
          <span class="product-card__stock-tag">
            ${semEstoque ? 'Esgotado' : `${parseFloat(p.estoque)} em estoque`}
          </span>
        </div>

        <span class="product-card__category">${escapeHtml(p.categoria_nome || 'Feira')}</span>
        <h3 class="product-card__title btnProductDetail" data-id="${p.id}" role="button" tabindex="0">
          ${escapeHtml(p.nome)}
        </h3>
        <p class="product-card__producer">
          <button type="button" class="btn-link-inline btnProducerDetail" data-id="${p.produtor}">${escapeHtml(produtorNome)}</button>
        </p>
        <p class="product-card__desc">${escapeHtml(p.descricao || 'Produto fresco da agricultura familiar.')}</p>

        <div class="product-card__action-row">
          <div class="product-card__price-wrap">
            <span class="product-card__price">${formatCurrency(p.preco)}</span>
            <span class="product-card__unit">/ ${escapeHtml(p.unidade_medida)}</span>
          </div>
          <button
            type="button"
            class="btn btn--primary btn--sm btnAddToCart"
            data-id="${p.id}"
            data-unit="${escapeHtml(p.unidade_medida)}"
            data-stock="${parseFloat(p.estoque)}"
            ${semEstoque ? 'disabled' : ''}>
            ${semEstoque ? 'Esgotado' : '＋ Adicionar'}
          </button>
        </div>
      </article>
    `;
  }).join('');
}

function renderPagination() {
  const container = document.getElementById('paginationControls');
  if (!container) return;

  if (catalogState.totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = `
    <div class="pagination">
      <button type="button" class="btn btn--outline btn--sm" id="btnPrevPage" ${catalogState.currentPage <= 1 ? 'disabled' : ''}>
        ◀ Anterior
      </button>
      <span class="pagination__info">Página ${catalogState.currentPage} de ${catalogState.totalPages} (${catalogState.totalCount} itens)</span>
      <button type="button" class="btn btn--outline btn--sm" id="btnNextPage" ${catalogState.currentPage >= catalogState.totalPages ? 'disabled' : ''}>
        Próxima ▶
      </button>
    </div>
  `;
}

// ── Detalhe do Produto e do Produtor ───────────────────────────────────────
export async function openProductDetail(productId) {
  const body = document.getElementById('productDetailBody');
  if (!body) return;

  body.innerHTML = '<div class="catalog-loading"><div class="spinner"></div><p>Carregando detalhes...</p></div>';
  openModal('productDetailModalOverlay');

  try {
    const [resProd, resAv] = await Promise.all([
      apiFetch(`/produtos/${productId}/`),
      apiFetch(`/avaliacoes/?produto=${productId}`),
    ]);
    if (!resProd.ok) throw new Error('Produto não encontrado.');
    const p = await resProd.json();
    const avData = resAv.ok ? await resAv.json() : { results: [] };
    const avaliacoes = avData.results || [];
    const semEstoque = parseFloat(p.estoque) <= 0;
    const customImgUrl = p.imagem ? safeUrl(p.imagem, '') : '';
    const imgUrl = customImgUrl || '/static/assets/logo-icon.webp';
    const imgClass = customImgUrl ? '' : 'product-card__img--default';

    body.innerHTML = `
      <div class="detail-grid">
        <div class="detail-img-wrap">
          <img src="${escapeHtml(imgUrl)}" alt="${escapeHtml(p.nome)}" class="${imgClass}" />
        </div>
        <div class="detail-info">
          <div class="detail-badges">
            ${typeBadges[p.tipo_producao] || ''}
            <span class="badge badge--outline">${escapeHtml(p.categoria_nome || '')}</span>
          </div>
          <h3>${escapeHtml(p.nome)}</h3>
          <p class="text-muted">
            Produzido por:
            <button type="button" class="btn-link-inline btnProducerDetail" data-id="${p.produtor}">${escapeHtml(p.produtor_nome)}</button>
          </p>
          <p class="detail-desc">${escapeHtml(p.descricao || 'Colhido diretamente pelo produtor familiar.')}</p>
          <div class="detail-price-row">
            <div>
              <strong class="detail-price">${formatCurrency(p.preco)}</strong>
              <span class="text-muted">/ ${escapeHtml(p.unidade_medida)}</span>
            </div>
            <span class="text-muted">Disponível: ${parseFloat(p.estoque)}</span>
          </div>
          <div class="detail-buy-row">
            <input type="number" id="detailProductQty" class="form-input" value="${Math.min(getUnitStep(p.unidade_medida).min, parseFloat(p.estoque) || getUnitStep(p.unidade_medida).min)}" min="${getUnitStep(p.unidade_medida).min}" max="${parseFloat(p.estoque) || getUnitStep(p.unidade_medida).min}" step="${getUnitStep(p.unidade_medida).step}" aria-label="Quantidade" ${semEstoque ? 'disabled' : ''} />
            <button type="button" class="btn btn--cta btn--lg" id="btnDetailAddToCart" data-id="${p.id}" ${semEstoque ? 'disabled' : ''}>
              ${semEstoque ? 'Esgotado' : 'Adicionar ao Carrinho'}
            </button>
          </div>
        </div>
      </div>

      <div class="detail-reviews">
        <h4>⭐ Avaliações de Clientes (${avaliacoes.length})</h4>
        ${avaliacoes.length === 0
          ? '<p class="text-muted">Ainda não há avaliações para este produto.</p>'
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
      </div>
    `;

    document.getElementById('btnDetailAddToCart')?.addEventListener('click', () => {
      const { min } = getUnitStep(p.unidade_medida);
      const qty = parseFloat(document.getElementById('detailProductQty')?.value || String(min)) || min;
      addToCart(p.id, qty);
    });
  } catch (err) {
    body.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

export async function openProducerDetail(producerId) {
  const body = document.getElementById('producerDetailBody');
  if (!body) return;

  body.innerHTML = '<div class="catalog-loading"><div class="spinner"></div><p>Carregando produtor...</p></div>';
  openModal('producerDetailModalOverlay');

  try {
    const [resProd, resAv] = await Promise.all([
      apiFetch(`/produtores/${producerId}/`),
      apiFetch(`/avaliacoes/?produtor=${producerId}`),
    ]);
    if (!resProd.ok) throw new Error('Produtor não encontrado.');
    const p = await resProd.json();
    const avData = resAv.ok ? await resAv.json() : { results: [] };
    const avaliacoes = avData.results || [];

    body.innerHTML = `
      <div class="producer-detail-head">
        <div class="producer-card__avatar">
          ${renderProducerAvatarImg(p)}
        </div>
        <div>
          <h3>${escapeHtml(p.nome_propriedade)}</h3>
          <p class="producer-card__location">📍 ${escapeHtml(p.cidade_uf || 'Agricultura Familiar Local')}</p>
        </div>
      </div>
      <p class="detail-desc">${escapeHtml(p.descricao || 'Produção rural familiar direta.')}</p>
      <div class="producer-card__badges" style="margin-bottom: var(--space-4);">
        ${p.aceita_pix ? PIX_BADGE_HTML : ''}
        ${p.possui_maquininha ? '<span class="payment-badge">💳 Cartão</span>' : ''}
        ${p.aceita_dinheiro ? '<span class="payment-badge">💵 Dinheiro</span>' : ''}
        <span class="badge badge--produtos">${p.total_produtos || 0} produto(s) ativo(s)</span>
      </div>

      <button type="button" class="btn btn--primary btn--full" id="btnFilterByProducer" data-id="${p.id}" data-name="${escapeHtml(p.nome_propriedade)}">
        Ver produtos deste produtor no catálogo
      </button>

      <div class="detail-reviews">
        <h4>⭐ Avaliações da Propriedade (${avaliacoes.length})</h4>
        ${avaliacoes.length === 0
          ? '<p class="text-muted">Ainda não há avaliações registradas para este produtor.</p>'
          : avaliacoes.map(a => `
            <div class="review-item">
              <div class="review-item__head">
                <strong>${escapeHtml(a.cliente_nome || 'Cliente')}</strong>
                <span>${'⭐'.repeat(a.nota)}</span>
              </div>
              <p>${escapeHtml(a.comentario || '')}</p>
            </div>
          `).join('')}
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div class="auth-error">${escapeHtml(err.message)}</div>`;
  }
}

// ── Estatísticas Públicas ──────────────────────────────────────────────────
export async function loadStatistics() {
  const statsEl = document.getElementById('heroSocialText');
  if (!statsEl) return;

  try {
    const res = await apiFetch('/estatisticas/');
    if (res.ok) {
      const data = await res.json();
      statsEl.innerHTML = `
        <span class="hero__stat-item"><strong>${Number(data.familias_atendidas_semana) || 0}</strong> famílias atendidas esta semana</span>
        <span class="hero__stat-sep" aria-hidden="true">•</span>
        <span class="hero__stat-item"><strong>${Number(data.total_produtores) || 0}</strong> produtores cadastrados</span>
        <span class="hero__stat-sep" aria-hidden="true">•</span>
        <span class="hero__stat-item"><strong>${Number(data.total_produtos) || 0}</strong> produtos frescos</span>
      `;
    }
  } catch (_) {}
}

// ── Vitrine dos Produtores ─────────────────────────────────────────────────
export async function loadProducers() {
  const container = document.getElementById('producerShowcase');
  if (!container) return;

  try {
    const res = await apiFetch('/produtores/');
    if (!res.ok) return;

    const data = await res.json();
    const produtores = data.results || data || [];
    if (produtores.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-state__icon">🚜</span>
          <p>Nenhum produtor aprovado cadastrado ainda.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = produtores.map(p => {
      return `
        <article class="producer-card">
          <div class="producer-card__top">
            <div class="producer-card__avatar">
              ${renderProducerAvatarImg(p)}
            </div>
            <div class="producer-card__header">
              <h3>${escapeHtml(p.nome_propriedade)}</h3>
              <span class="producer-card__location">📍 ${escapeHtml(p.cidade_uf || p.cidade || 'Região')}</span>
            </div>
          </div>
          <p class="producer-card__desc">${escapeHtml(p.descricao || 'Produção familiar local e sustentável.')}</p>
          <div class="producer-card__footer">
            <div class="producer-card__badges">
              ${p.aceita_pix ? PIX_BADGE_HTML : ''}
              ${p.possui_maquininha ? '<span class="payment-badge">💳 Cartão</span>' : ''}
              ${p.aceita_dinheiro ? '<span class="payment-badge">💵 Dinheiro</span>' : ''}
              <span class="badge badge--produtos">${Number(p.total_produtos) || 0} produto(s)</span>
            </div>
            <button type="button" class="btn btn--outline btn--sm btnProducerDetail" data-id="${p.id}">
              Ver propriedade e produtos
            </button>
          </div>
        </article>
      `;
    }).join('');
  } catch (_) {}
}
