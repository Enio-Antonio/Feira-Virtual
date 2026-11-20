# 🌱 Feira Virtual

Marketplace de **venda direta da agricultura familiar**: conecta produtores rurais, entregadores e clientes, sem atravessadores.

**Stack:** Django 6 · Django REST Framework · SimpleJWT · drf-spectacular · SQLite/MySQL · Frontend em HTML/CSS/JS puro (ES Modules) servido pelo Django + WhiteNoise.

## 📌 Sumário

[Funcionalidades](#-funcionalidades) · [Como rodar](#-como-rodar) · [Contas de demonstração](#-contas-de-demonstração) · [Configuração](#-configuração-env) · [Estrutura](#-estrutura) · [API](#-api) · [Fluxo de pedido](#-fluxo-de-pedido) · [Testes e CI](#-testes-e-ci) · [Identidade visual](#-identidade-visual) · [Roadmap](#-roadmap)

---

## ✨ Funcionalidades

| Perfil | O que faz |
|---|---|
| 🛒 **Cliente** | Catálogo com busca/filtros, carrinho, checkout (retirada ou entrega), Pix, acompanhamento de pedidos, avaliações, reclamações e endereços (ViaCEP) |
| 🌾 **Produtor** | Cadastro de produtos com foto, controle de estoque, aceite/recusa de pedidos, resumo de vendas e avaliações |
| 🛵 **Entregador** | Entregas disponíveis, aceitar, "saiu para entrega" e confirmar entrega |
| 🛡️ **Admin** | Indicadores, aprovar/suspender produtores, ocultar produtos, moderar reclamações e usuários (com log de auditoria) |

**Destaques técnicos:** checkout transacional com lock de estoque · notificações por e-mail (interface pronta para WhatsApp) · Pix mock com webhook HMAC · LGPD (exportar/excluir dados) · CSP estrita · throttling em autenticação · dark mode · PWA básico.

---

## 🚀 Como rodar

### Desenvolvimento local (SQLite)

```bash
cd feira_virtual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env

export DJANGO_DEBUG=1
python manage.py migrate
python manage.py seed_demo      # dados de demonstração (só com DEBUG=1)
python manage.py runserver
```

Acesse: **http://127.0.0.1:8000/** · Health: `/api/health/` · Swagger: `/api/docs/` (restrito a admin, ou `ENABLE_SWAGGER=1`).

### Docker (MySQL 8.4 + Gunicorn, usuário não-root)

```bash
cp .env.example .env            # defina senhas e DJANGO_SECRET_KEY
docker compose up --build -d
docker compose exec web python manage.py migrate
```

### Produção — checklist

1. `DJANGO_DEBUG=0` + `DJANGO_SECRET_KEY` forte (50+ caracteres).
2. Restringir `DJANGO_ALLOWED_HOSTS`, `CORS_*` e `CSRF_TRUSTED_ORIGINS` ao seu domínio.
3. `DB_ENGINE=mysql` e SMTP real em `EMAIL_*`.
4. `python manage.py collectstatic --no-input` e `python manage.py check --deploy`.
5. Servir com `gunicorn config.wsgi:application`. Para múltiplas instâncias, mover `/media/` para S3/Cloudflare R2 (`django-storages`).

---

## 👥 Contas de demonstração

Criadas por `python manage.py seed_demo` (apenas desenvolvimento; `--reset` recria tudo):

| Perfil | Usuário | Senha |
|---|---|---|
| Cliente | `cliente_demo` | `cliente-demo-2024` |
| Produtor | `produtor_demo` | `produtor-demo-2024` |
| Entregador | `entregador_demo` | `entregador-demo-2024` |
| Admin | `admin` | `admin-demo-2024` |

---

## ⚙️ Configuração (`.env`)

Veja todas as opções em [`.env.example`](.env.example). Principais:

| Variável | Padrão | Descrição |
|---|---|---|
| `DJANGO_DEBUG` | `0` | `1` apenas em desenvolvimento |
| `DJANGO_SECRET_KEY` | — | Obrigatória quando `DEBUG=0` |
| `DJANGO_ALLOWED_HOSTS` | vazio | Hosts permitidos (separados por vírgula) |
| `DB_ENGINE` | `sqlite` | `sqlite` ou `mysql` (+ `DB_NAME/USER/PASSWORD/HOST/PORT`) |
| `ENABLE_SWAGGER` | `0` | `1` libera `/api/docs/` publicamente |
| `CORS_ALLOW_ALL_ORIGINS` / `CORS_ALLOWED_ORIGINS` | `0` | Origens permitidas |
| `EMAIL_*` | console | Configuração SMTP |
| `THROTTLE_*` | ver `.env.example` | Limites de requisições (login, registro, recuperação de senha) |
| `PIX_WEBHOOK_SECRET` | dev | Segredo HMAC do webhook Pix |

---

## 📦 Estrutura

```text
feira_virtual/
├── config/        # settings, urls, middleware (CSP) e validadores de upload
├── usuarios/      # usuário (4 perfis), endereços, auth JWT, LGPD, seed_demo
├── catalogo/      # categorias, produtos, vitrine de produtores, estatísticas
├── pedidos/       # carrinho, checkout, estados do pedido, notificações, Pix
├── avaliacoes/    # avaliações e reclamações
├── painel/        # moderação admin e log de auditoria
├── frontend/      # index.html, style.css, main.js, js/ (módulos ES) e assets/ (logos, favicons)
├── Dockerfile · docker-compose.yml · requirements*.txt
└── .github/workflows/ci.yml
```

---

## 🔌 API

Documentação completa via Swagger (`/api/docs/`). Resumo:

| Área | Endpoints principais |
|---|---|
| **Auth** | `POST /api/auth/login/` · `refresh/` · `logout/` · `registro/{cliente,produtor,entregador}/` · `recuperar-senha/` · `redefinir-senha/` |
| **Perfil / LGPD** | `GET/PATCH /api/perfil/` · `perfil/produtor/` · `perfil/entregador/` · `perfil/exportar-dados/` · `DELETE perfil/excluir-conta/` · `/api/enderecos/` |
| **Catálogo** | `GET /api/categorias/` · `produtos/` (`?search=&categoria=&tipo_producao=&produtor=&ordering=`) · `produtores/` · `estatisticas/` · `/api/produtor/produtos/` |
| **Pedidos** | `/api/carrinho/` · `carrinho/itens/` · `/api/pedidos/` · `pedidos/{id}/cancelar/` · `pedidos/{id}/pix/` · `POST pedidos/pix/webhook/` |
| **Produtor** | `/api/produtor/pedidos/` (`aceitar`, `recusar`, `status`, `vendas`) · `/api/produtor/avaliacoes/` |
| **Entregador** | `/api/entregas/` (`aceitar`, `saiu-para-entrega`, `confirmar`) |
| **Avaliações** | `/api/avaliacoes/` · `/api/reclamacoes/` |
| **Admin** | `/api/admin/indicadores/` · `/api/admin/{usuarios,produtores,produtos,pedidos,reclamacoes}/` |
| **Sistema** | `GET /api/health/` |

---

## 🔄 Fluxo de pedido

```text
PENDENTE ─▶ ACEITO ─▶ EM_PREPARO ─▶ PRONTO ─▶ EM_ENTREGA ─▶ CONCLUIDO
   │          │            │           └──(retirada)────────▶ CONCLUIDO
   ├─▶ RECUSADO (produtor)
   └─────────────────────────────────▶ CANCELADO (cliente; estoque devolvido)
```

- O carrinho gera **um pedido por produtor**.
- O estoque é travado no checkout (`select_for_update`), baixado no aceite e devolvido em cancelamento/recusa.
- Itens do pedido guardam nome e preço da data da compra.
- A chave Pix só é exibida ao cliente com pedido ativo (ou ao produtor/admin).

---

## 🧪 Testes e CI

```bash
python manage.py test                                   # 23 testes
coverage run manage.py test && coverage report          # cobertura atual: 89%
python manage.py check --deploy                         # com DEBUG=0 e SECRET_KEY definida
python manage.py spectacular --validate > /dev/null     # valida o schema OpenAPI
```

O GitHub Actions (`.github/workflows/ci.yml`) roda Ruff, `check`, `check --deploy`, `collectstatic` e testes com cobertura a cada push/PR na `main`.

---

## 🎨 Identidade visual

Paleta extraída da logo oficial (contraste WCAG AA):

| Token | Cor | Uso |
|---|---|---|
| `--color-primary` | `#246F11` | Verde principal |
| `--color-primary-dark` | `#1B4312` | Hover / alto contraste |
| `--color-primary-light` | `#67AE25` | Realces |
| `--color-cta` | `#F7990C` | Botões de ação e foco |

Logos em `frontend/assets/` (PNG e WebP 1x/2x): versão clara, versão para **dark mode** (troca automática via `data-theme`), ícone, favicons, `og-image` e `manifest.webmanifest`.

---

## 🔮 Roadmap

- Gateway Pix real (Mercado Pago / Efí / Asaas) e WhatsApp oficial.
- Tokens JWT em cookies `httpOnly`.
- Fontes Inter/Fraunces self-hosted e auditoria Lighthouse.
- Frete automático por CEP e mídia em S3/Cloudflare R2.
