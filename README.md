# 🌱 Feira Virtual — Plataforma de Venda Direta da Agricultura Familiar

Plataforma full-stack (Backend API + Frontend modular integrado) para conexão direta entre **produtores rurais da agricultura familiar**, **entregadores parceiros**, **compradores finais** e **administradores**, eliminando atravessadores e promovendo alimentos frescos com preço justo.

---

## 📌 Sumário

- [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Como Rodar o Projeto](#-como-rodar-o-projeto)
- [Contas de Demonstração (`seed_demo`)](#-contas-de-demonstração-seed_demo)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Identidade Visual e Paleta](#-identidade-visual-e-paleta)
- [Principais Endpoints da API](#-principais-endpoints-da-api)
- [Fluxo de Pedido e Regras de Negócio](#-fluxo-de-pedido-e-regras-de-negócio)
- [Decisões Técnicas Registradas](#-decisões-técnicas-registradas)
- [Testes, Cobertura e CI](#-testes-cobertura-e-ci)
- [Roadmap](#-roadmap)

---

## 🏗 Visão Geral e Arquitetura

- **Backend:** Python + Django 6.x + Django REST Framework + SimpleJWT + `drf-spectacular`.
- **Frontend:** HTML5 semântico, CSS3 moderno (Design Tokens + Dark Mode) e JavaScript puro em **ES Modules nativos** (`frontend/js/*.js`), sem dependência de bundlers ou frameworks pesados.
- **Servimento de Estáticos e Mídia:**
  - Arquivos estáticos do frontend (`style.css`, `main.js`, `js/*.js`, `assets/*`) são servidos pelo **WhiteNoise** (`CompressedManifestStaticFilesStorage`) com compressão e cache imutável em produção, enquanto `/` renderiza `frontend/index.html` via Django `TemplateView`.
  - Uploads de imagem (`media/`) passam por validação de extensão, tamanho (máx. 5 MB) e assinatura binária via Pillow (`config/validators.py`) e são entregues em `/media/` por rota controlada contra *path traversal* (ou podem ser migrados para S3 / Cloudflare R2 via `django-storages`).
- **Banco de Dados:** Suporte a **SQLite** (desenvolvimento ágil) e **MySQL 8.4** via **PyMySQL** puro (sem necessidade de compilar `gcc`/`libmysqlclient-dev`), alternável via `DB_ENGINE`.
- **Segurança:** `DEBUG=0` por padrão (*fail-safe*), `DJANGO_SECRET_KEY` obrigatória fora de `DEBUG`, CSP restritivo (`ContentSecurityPolicyMiddleware`), throttles dedicados para autenticação (`login`, `registro`, `recuperar_senha`), cabeçalhos HSTS/SSL configurados para produção, logs de auditoria administrativa/LGPD e Swagger restrito a administradores por padrão (`ENABLE_SWAGGER=0`).

---

## 📦 Estrutura do Projeto

```text
feira_virtual/
├── .github/workflows/
│   └── ci.yml                 # Pipeline CI: Ruff, Django check, check --deploy, collectstatic e coverage
├── avaliacoes/                # Avaliações (produto/produtor após compra concluída) e reclamações
├── catalogo/                  # Categorias, produtos, filtros, vitrine de produtores e estatísticas reais
├── config/
│   ├── middleware.py          # Content-Security-Policy (CSP)
│   ├── settings.py            # Configurações híbridas, segurança, WhiteNoise, DRF, logging estruturado
│   ├── urls.py                # Rotas da API, saúde (/api/health/), frontend (TemplateView) e /media/
│   └── validators.py          # Validação binária e de tamanho de uploads de imagem (Pillow)
├── frontend/
│   ├── assets/                # Logos recortadas (PNG/WebP 1x/2x, variante branca), favicons, og-image e PWA manifest
│   ├── js/
│   │   ├── admin.js           # Painel de moderação (indicadores, aprovar/suspender, ocultar, reclamações, usuários)
│   │   ├── api.js             # Cliente centralizado com auto-refresh JWT, fila 401 e loading bar
│   │   ├── auth.js            # Login, registro multi-perfil, perfil, recuperação de senha e LGPD
│   │   ├── cart.js            # Carrinho de compras, drawer lateral e checkout
│   │   ├── delivery.js        # Painel do entregador (disponíveis, aceitar, saiu para entrega, confirmar, veículo)
│   │   ├── orders.js          # Pedidos do cliente, timeline, Pix QR/copia-e-cola, avaliações, reclamações e ViaCEP
│   │   ├── producer.js        # Painel do produtor (CRUD produtos + upload, pedidos, vendas e propriedade)
│   │   ├── products.js        # Catálogo paginado, filtros, detalhes de produto/produtor e vitrine
│   │   └── ui.js              # Toasts aria-live, focus trap/ESC nos modais, skeletons, máscaras e QR SVG
│   ├── index.html             # Template único com {% static %} e sem requisições externas bloqueantes
│   ├── main.js                # Orquestrador ES Module principal
│   └── style.css              # Design System (regra 60-30-10, Light/Dark mode, prefers-reduced-motion)
├── painel/                    # Indicadores administrativos, moderação e modelo LogAuditoria (admin/LGPD)
├── pedidos/
│   ├── notificacoes.py        # Camada abstrata de notificações (E-mail console/SMTP + interface WhatsApp)
│   ├── pix.py                 # Gateway Pix abstrato (Mock dev + validação de assinatura HMAC de webhook)
│   ├── services.py            # Checkout transacional com select_for_update(), estoque e máquina de estados
│   └── ...
├── usuarios/
│   ├── management/commands/
│   │   └── seed_demo.py       # Popula dados de demonstração (exclusivo com DEBUG=1)
│   └── ...                    # Usuário customizado (4 perfis), endereços e endpoints LGPD
├── Dockerfile                 # Imagem Python 3.12-slim não-root com collectstatic e HEALTHCHECK (/api/health/)
├── docker-compose.yml         # MySQL 8.4 + App configurados via .env
├── requirements.txt           # Dependências de produção
└── requirements-dev.txt       # Ferramentas de desenvolvimento (pytest, coverage, ruff)
```

---

## 💻 Como Rodar o Projeto

### 1. Desenvolvimento Local (SQLite)

```bash
# 1. Acesse o projeto e crie/ative o ambiente virtual
cd feira_virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Copie as variáveis de ambiente de exemplo (ajuste se desejar)
cp .env.example .env

# 4. Aplique as migrações e crie dados de demonstração (requer DJANGO_DEBUG=1)
DJANGO_DEBUG=1 DB_ENGINE=sqlite python manage.py migrate
DJANGO_DEBUG=1 DB_ENGINE=sqlite python manage.py seed_demo

# 5. Inicie o servidor
DJANGO_DEBUG=1 DB_ENGINE=sqlite python manage.py runserver
```

Acesse:
- **Aplicação Web:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Healthcheck API:** [http://127.0.0.1:8000/api/health/](http://127.0.0.1:8000/api/health/)
- **Documentação Swagger:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/) *(por padrão exige login admin ou `ENABLE_SWAGGER=1`)*

### 2. Docker Compose (MySQL 8.4 + Aplicação)

```bash
# Configure suas senhas e DJANGO_SECRET_KEY no .env antes de subir
cp .env.example .env

# Suba o banco MySQL e a aplicação Gunicorn (executa como usuário não-root `appuser`)
docker compose up --build -d

# Execute migrações dentro do container
docker compose exec web python manage.py migrate
```

### 3. Produção (Checklist Essencial)

1. Defina `DJANGO_DEBUG=0` e uma `DJANGO_SECRET_KEY` aleatória com 50+ caracteres.
2. Restrinja `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOW_ALL_ORIGINS=0`, `CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` ao domínio oficial.
3. Configure `DB_ENGINE=mysql` e um servidor SMTP real em `EMAIL_*`.
4. Gere os estáticos com cache de hash (`python manage.py collectstatic --no-input`) e valide a configuração de segurança:
   ```bash
   DJANGO_DEBUG=0 python manage.py check --deploy
   ```
5. Suba via WSGI/Gunicorn (`gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3`).
6. **Armazenamento de Mídia (`/media/`) em múltiplas instâncias:** Em single-server, o volume persistente `/app/media` + rota controlada `media_serve_view` atende aos uploads. Para escalar horizontalmente, configure `django-storages` com **Amazon S3** ou **Cloudflare R2**.

---

## 👥 Contas de Demonstração (`seed_demo`)

Em ambiente de desenvolvimento (`DJANGO_DEBUG=1`), execute:

```bash
DJANGO_DEBUG=1 python manage.py seed_demo
# ou para recriar os dados de exemplo do zero:
DJANGO_DEBUG=1 python manage.py seed_demo --reset
```

> O comando recusa execução quando `DJANGO_DEBUG=0`, evitando qualquer inserção acidental em produção. Credenciais reais jamais devem constar no repositório.

Contas de demonstração criadas localmente pelo `seed_demo`:

| Perfil | Usuário | E-mail | Senha de Teste |
|---|---|---|---|
| **Cliente** | `cliente_demo` | `cliente@demo.com` | `cliente-demo-2024` |
| **Produtor** | `produtor_demo` | `produtor@demo.com` | `produtor-demo-2024` |
| **Entregador** | `entregador_demo` | `entregador@demo.com` | `entregador-demo-2024` |
| **Administrador** | `admin` | `admin@demo.com` | `admin-demo-2024` |

---

## ⚙ Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `DJANGO_DEBUG` | `0` | Ativa modo debug (`1` em dev, `0` obrigatório em produção) |
| `DJANGO_SECRET_KEY` | *(obrigatória se DEBUG=0)* | Chave criptográfica do Django (>= 50 caracteres em produção) |
| `DJANGO_ALLOWED_HOSTS` | `*` (se DEBUG=1) / vazio | Lista separada por vírgula dos hosts permitidos |
| `ENABLE_SWAGGER` | `0` | `1` libera `/api/docs/` publicamente; `0` restringe a administradores |
| `SECURE_SSL_REDIRECT` | `1` (se DEBUG=0) | Redireciona HTTP para HTTPS fora do modo debug |
| `LOG_LEVEL` | `INFO` | Nível dos logs estruturados em stdout |
| `DB_ENGINE` | `sqlite` | `sqlite` ou `mysql` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | — | Credenciais e endereço do banco MySQL |
| `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOWED_ORIGINS` | `1` (se DEBUG=1) / `0` | Controle de origens permitidas no CORS |
| `CSRF_TRUSTED_ORIGINS` | localhost + túneis dev | Origens confiáveis para submissões CSRF |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Console em DEBUG | Configuração de envio de e-mail |
| `THROTTLE_ANON`, `THROTTLE_USER`, `THROTTLE_LOGIN`, `THROTTLE_REGISTRO`, `THROTTLE_RECUPERAR_SENHA` | `100/m`, `1000/m`, `10/m`, `5/m`, `5/m` | Limites de taxa por IP/usuário |
| `PIX_WEBHOOK_SECRET` | Chave dev | Segredo HMAC-SHA256 para validar webhooks de confirmação Pix |

---

## 🎨 Identidade Visual e Paleta

Os tokens visuais foram calibrados a partir das cores reais extraídas da logo oficial em `frontend/assets/`, respeitando a regra **60-30-10** e contraste **WCAG 2.1 AA**:

| Token CSS | Hex | Aplicação |
|---|---|---|
| `--color-primary` | `#246F11` | Verde principal (cabeçalho, ações primárias, links ativos) |
| `--color-primary-dark` | `#1B4312` | Hover primário e fundos de alto contraste |
| `--color-primary-light` | `#67AE25` | Realces sutis e detalhes orgânicos |
| `--color-primary-tint` | `#E8F5E0` | Fundos suaves para badges e cards selecionados |
| `--color-cta` | `#F7990C` | Laranja CTA (botões de conversão, foco visível) |
| `--bg-base` / `--bg-card` | `#FAFAF8` / `#FFFFFF` | Base neutra clara (`#141712` / `#272B23` no Dark Mode) |

**Variantes da logo em `frontend/assets/`:**
- `logo-horizontal.png` / `.webp` e `-2x.webp` — logo recortada com transparência para fundos claros;
- `logo-horizontal-white.png` / `.webp` e `-2x.webp` — variante clara/monocromática ativada automaticamente quando `[data-theme="dark"]`;
- `logo-icon.png` / `.webp` — apenas o símbolo da cesta e folhas (fallback de produto e ícone quadrado);
- `favicon.ico`, `favicon-32.png`, `apple-touch-icon.png` (180px), `icon-192.png`, `icon-512.png`, `manifest.webmanifest`, `og-image.png` (1200×630).

---

## 🔌 Principais Endpoints da API

### Autenticação, Perfis & LGPD (`/api/`)
- `POST /api/auth/login/` — Obtém tokens JWT (`access` e `refresh`) *(throttle dedicado)*.
- `POST /api/auth/refresh/` — Renova `access` token.
- `POST /api/auth/logout/` — Coloca `refresh` token na blacklist.
- `POST /api/auth/registro/cliente/` | `/produtor/` | `/entregador/` — Cadastros específicos por perfil.
- `POST /api/auth/recuperar-senha/` | `POST /api/auth/redefinir-senha/` — Fluxo completo de recuperação de senha.
- `GET/PATCH /api/perfil/` — Dados do usuário autenticado.
- `GET/PATCH /api/perfil/produtor/` | `/perfil/entregador/` — Gestão do perfil profissional (incluindo upload de foto da propriedade).
- `GET /api/perfil/exportar-dados/` | `DELETE /api/perfil/excluir-conta/` — Portabilidade JSON e anonimização LGPD (com registro em `LogAuditoria`).
- `CRUD /api/enderecos/` — Endereços de entrega do usuário.

### Catálogo & Público (`/api/`)
- `GET /api/categorias/` — Categorias ativas (admin também cria/edita).
- `GET /api/produtos/` — Catálogo paginado (`?page=`, `?search=`, `?categoria=`, `?tipo_producao=`, `?produtor=`, `?ordering=`).
- `GET /api/produtores/` — Vitrine pública dos produtores aprovados (sem expor chave Pix).
- `GET /api/estatisticas/` — Contadores reais em tempo real (famílias atendidas na semana, produtores, produtos e pedidos concluídos).
- `CRUD /api/produtor/produtos/` — Gestão dos próprios produtos pelo produtor (incluindo upload de foto validado).

### Carrinho, Pedidos, Pix & Entregas (`/api/`)
- `GET/DELETE /api/carrinho/` e `POST/PATCH/DELETE /api/carrinho/itens/` — Gestão do carrinho.
- `GET/POST /api/pedidos/` — Histórico e checkout (divide automaticamente o carrinho por produtor).
- `POST /api/pedidos/{id}/cancelar/` — Cancelamento pelo cliente (com motivo opcional).
- `GET /api/pedidos/{id}/pix/` — Geração de cobrança Pix mock (chave e payload copia-e-cola).
- `POST /api/pedidos/pix/webhook/` — Webhook com verificação de assinatura HMAC-SHA256 (`X-Signature`).
- `GET /api/produtor/pedidos/`, `POST .../aceitar/`, `.../recusar/`, `.../status/`, `GET .../vendas/` — Fluxo operacional e faturamento do produtor.
- `GET /api/entregas/?escopo=disponiveis|minhas`, `POST .../aceitar/`, `.../saiu-para-entrega/`, `.../confirmar/` — Fluxo do entregador.

### Avaliações, Moderação Admin & Sistema
- `GET/POST /api/avaliacoes/` e `GET /api/produtor/avaliacoes/` — Avaliação por item ou produtor (exclusivo após compra concluída).
- `GET/POST /api/reclamacoes/` — Registro e acompanhamento de reclamações do cliente.
- `GET /api/admin/indicadores/` e gestão em `/api/admin/{usuarios,produtores,produtos,pedidos,reclamacoes}/` — Moderação completa com `LogAuditoria`.
- `GET /api/health/` — Healthcheck de aplicação e conectividade com banco de dados.

---

## ⚖️ Fluxo de Pedido e Regras de Negócio

```text
PENDENTE ──(produtor aceita)──▶ ACEITO ──▶ EM_PREPARO ──▶ PRONTO ──▶ EM_ENTREGA ──▶ CONCLUIDO
   │                              │            │             │          (ou RETIRADA direto)
   ├──(produtor recusa)──▶ RECUSADO            ▼             ▼
   └──(cliente cancela)──────────────▶ CANCELADO (estorna estoque automaticamente)
```

1. **Separação por Produtor:** Itens de produtores distintos no mesmo carrinho geram um pedido independente para cada produtor.
2. **Proteção de Concorrência & Estoque:** O checkout usa `transaction.atomic()` e `select_for_update()` nos produtos antes de criar os pedidos. A baixa efetiva ocorre no aceite do produtor e é estornada transacionalmente em caso de cancelamento ou recusa.
3. **Privacidade Pix (LGPD):** A chave Pix do produtor não aparece na vitrine pública nem em pedidos cancelados/recusados; só fica acessível para o cliente com pedido ativo ou para o próprio produtor/admin.
4. **Histórico Imutável:** `ItemPedido` congela nome, unidade e preço unitário no momento da compra.

---

## 📝 Decisões Técnicas Registradas

- **`DEBUG=0` padrão + Parser `.env` próprio:** Garante comportamento *fail-safe* se `DJANGO_DEBUG` não for definida em produção, mantendo zero dependências extras de parsing mantendo compatibilidade total com variáveis de sistema/Docker.
- **SQLite como padrão no desenvolvimento:** Facilita inicialização imediata com `.venv` e testes automatizados mantendo MySQL 8.4 + PyMySQL prontos para produção.
- **JWT no cliente + CSP restritiva:** O frontend em ES Modules mantém autenticação via `Authorization: Bearer` (com auto-refresh centralizado) combinada com `Content-Security-Policy` estrita (`script-src 'self'`), sanitização via `escapeHtml()`/`safeUrl()` e ausência total de scripts inline. A migração para cookies `httpOnly` + CSRF duplo está mapeada no roadmap.
- **Tipografia local sem requisições externas:** Removidas dependências externas de Google Fonts para maximizar desempenho e compatibilidade com CSP estrita (`font-src 'self'`). Arquivos `.woff2` (Inter/Fraunces) podem ser adicionados posteriormente em `frontend/assets/fonts/`.
- **Pix Gateway & Notificações desacoplados:** Implementação funcional de `MockPixGateway` + `CentralNotificacoes` (e-mail console em dev + interface pronta para WhatsApp) para substituição direta por SDK/API oficial em produção.

---

## 🧪 Testes, Cobertura e CI

A suíte conta com **23 testes automatizados** cobrindo todos os módulos (`usuarios`, `catalogo`, `pedidos`, `avaliacoes`, `painel`) e atingindo **89% de cobertura**:

```bash
# Executar testes padrão
DB_ENGINE=sqlite .venv/bin/python manage.py test

# Executar com relatório de cobertura
DB_ENGINE=sqlite .venv/bin/coverage run manage.py test
DB_ENGINE=sqlite .venv/bin/coverage report --omit='*/.venv/*,manage.py,config/wsgi.py,config/asgi.py,*/migrations/*,*/tests.py'

# Checagens de estáticos, deploy e OpenAPI
DB_ENGINE=sqlite .venv/bin/python manage.py collectstatic --no-input
DJANGO_DEBUG=1 DB_ENGINE=sqlite .venv/bin/python manage.py check
DJANGO_DEBUG=0 DJANGO_SECRET_KEY=chave-de-teste-com-mais-de-cinquenta-caracteres-1234567890 DB_ENGINE=sqlite .venv/bin/python manage.py check --deploy
DJANGO_DEBUG=1 DB_ENGINE=sqlite .venv/bin/python manage.py spectacular --validate > /dev/null
```

O pipeline em `.github/workflows/ci.yml` executa Ruff (`ruff check .`), checagens do Django (`check` e `check --deploy`), `collectstatic` e testes com cobertura em todo `push`/`pull_request` para `main`.

---

## 🔮 Roadmap

- Substituir `MockPixGateway` por integração real (Mercado Pago, Efí ou Asaas).
- Ligar `NotificadorWhatsApp` a provedor oficial (Evolution API / Z-API / Twilio) e envio de e-mail transacional SMTP/SendGrid.
- Migrar tokens JWT do `localStorage` para cookies `httpOnly; Secure; SameSite=Lax` com rotação automática.
- Self-host opcional de fontes `.woff2` (`Inter` e `Fraunces`) em `frontend/assets/fonts/` e auditoria Lighthouse em produção.
- Cálculo automático de frete por CEP/faixa de distância e upload de mídia em bucket S3 / Cloudflare R2 via `django-storages`.
