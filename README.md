#  Feira Virtual — Plataforma de Venda Direta

Plataforma completa (Backend API + Frontend integrado) para conexão direta entre **produtores rurais da agricultura familiar**, **entregadores parceiros** e **compradores finais**, eliminando atravessadores e garantindo alimentos frescos com preço justo.

---

##  Sumário

- [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
- [Histórico de Atualizações](#-histórico-de-atualizações)
- [Como Rodar o Projeto](#-como-rodar-o-projeto)
  - [Opção 1: Inicialização Rápida (Recomendada)](#opção-1-inicialização-rápida-recomendada)
  - [Opção 2: Com Banco MySQL Local ou Docker](#opção-2-com-banco-mysql-local-ou-docker)
  - [Opção 3: Acesso Externo / Celular (ngrok ou Cloudflare)](#opção-3-acesso-externo--celular-ngrok-ou-cloudflare)
  - [Checklist de Produção](#checklist-de-produção)
- [Contas de Teste (seed_demo)](#-contas-de-teste-seed_demo)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Estrutura dos Módulos](#-estrutura-dos-módulos)
- [Principais Endpoints da API](#-principais-endpoints-da-api)
- [Fluxo de Pedido e Regras de Negócio](#-fluxo-de-pedido-e-regras-de-negócio)
- [Design System e Identidade Visual](#-design-system-e-identidade-visual)
- [Testes e CI](#-testes-e-ci)
- [Próximos Passos](#-próximos-passos)

---

## Visão Geral e Arquitetura

O sistema é composto por:

- **Backend:** Python + Django 6.x + Django REST Framework + SimpleJWT.
- **Frontend:** HTML5 semântico, CSS3 moderno (Custom Properties) e JavaScript puro organizado em **ES Modules** (`frontend/js/`), servido de forma unificada pelo próprio Django na raiz (`/`).
- **Banco de Dados:** híbrido — roda de imediato com **SQLite** no desenvolvimento ou com **MySQL 8.x** em produção, configurável pelo `.env`.
- **Documentação da API:** Swagger interativo gerado via `drf-spectacular` (restrito a administradores por padrão).

**Perfis de usuário:**

| Perfil | O que faz na plataforma |
|---|---|
| 🛒 **Cliente** | Navega no catálogo, monta o carrinho, finaliza pedidos (retirada ou entrega), paga via Pix/cartão/dinheiro, acompanha o status, avalia e registra reclamações |
| 🌾 **Produtor** | Cadastra produtos com foto e estoque, aceita ou recusa pedidos, atualiza o status e acompanha vendas e avaliações |
| 🛵 **Entregador** | Vê entregas disponíveis, aceita, marca "saiu para entrega" e confirma a entrega |
| 🛡️ **Administrador** | Aprova/suspende produtores, oculta produtos, modera reclamações e usuários, consulta indicadores |

---

## 🚀 Histórico de Atualizações

Principais melhorias implementadas até agora:

### 1. Banco de Dados Flexível (MySQL e SQLite)
- **Driver PyMySQL integrado:** hook em `config/__init__.py` com `pymysql.install_as_MySQLdb()`, sem compilar pacotes C (`mysqlclient`).
- **Alternância sem mudar código:** `DB_ENGINE=sqlite` (padrão) ou `DB_ENGINE=mysql` no `.env`.

### 2. Identidade Visual Oficial
- **Logo integrada** na navbar, rodapé, favicon, ícones de app (PWA), `apple-touch-icon` e imagem de compartilhamento (`og-image`).
- **Variantes da logo:** versão clara, versão para **dark mode** (colorida, com troca automática), apenas ícone e formatos **WebP** com `srcset` 1x/2x.
- **Paleta extraída da logo real:** verde `#246F11`, verde-claro `#67AE25` e laranja `#F7990C`.
- **Meta tags** de SEO, Open Graph/Twitter Cards, `theme-color` e `manifest.webmanifest`.

### 3. Segurança e Produção
- **Configuração segura por padrão:** `DEBUG=0`, `DJANGO_SECRET_KEY` obrigatória fora do modo debug, HSTS, redirecionamento HTTPS e cookies seguros.
- **CSP estrita** (`script-src 'self'`) via middleware próprio, sem scripts inline, e sanitização de HTML no cliente (`escapeHtml`/`safeUrl`).
- **Throttling dedicado** para login, registro e recuperação de senha, além dos limites gerais (anônimos/autenticados).
- **CORS e CSRF configuráveis**, compatíveis com proxy reverso e túneis HTTPS (ngrok, Cloudflare).
- **Upload de mídia validado:** extensão, tamanho (máx. 5 MB) e assinatura real da imagem (Pillow); `/media/` servida por rota protegida contra *path traversal*.
- **Estáticos com WhiteNoise:** compressão e cache com hash, sem precisar de Nginx exclusivo.
- **Docker endurecido:** imagem sem `gcc`, execução como usuário não-root, `HEALTHCHECK` e endpoint `/api/health/`.
- **Swagger oculto** do público (somente admin, ou `ENABLE_SWAGGER=1`).

### 4. Pedidos, Pagamentos e Notificações
- **Número público do pedido**, taxa de entrega, previsão de entrega/retirada e motivo de recusa/cancelamento.
- **Checkout protegido contra concorrência** (`select_for_update`) com divisão automática por produtor.
- **Pix com gateway abstrato:** implementação *mock* para desenvolvimento (QR Code e copia-e-cola) e webhook com validação de assinatura HMAC.
- **Notificações de status** por e-mail (console em dev), com interface pronta para WhatsApp/push.
- **Chave Pix protegida:** só aparece para o cliente com pedido ativo (ou produtor/admin).

### 5. LGPD e Auditoria
- **Exportar dados** (JSON) e **excluir/anonimizar conta** pelo próprio usuário.
- **Log de auditoria** (`LogAuditoria`) para ações administrativas e eventos LGPD.
- **Logs estruturados** no stdout e erros da API padronizados.

### 6. Frontend Completo (todos os perfis)
- **Single-Server:** o Django serve a interface em `http://127.0.0.1:8000/`.
- **Código modular** (`api.js`, `auth.js`, `cart.js`, `products.js`, `orders.js`, `producer.js`, `delivery.js`, `admin.js`, `ui.js`) com cliente de API centralizado e renovação automática do token JWT.
- **Cliente:** catálogo paginado com busca, filtros e ordenação; detalhe de produto e produtor; carrinho; checkout; meus pedidos com linha do tempo e cancelamento; Pix com QR Code; avaliações; reclamações; endereços com busca de CEP (ViaCEP); edição de perfil e recuperação de senha.
- **Produtor / Entregador / Admin:** painéis próprios com CRUD de produtos e upload de foto, gestão de pedidos, entregas e moderação.
- **Cadastro multi-perfil:** escolha entre cliente, produtor e entregador.
- **Dados reais na home:** "famílias atendidas na semana" e vitrine de produtores vêm do banco de dados.
- **UX e acessibilidade:** skeleton loading, estados vazios, toasts com `aria-live`, foco preso e `ESC` nos modais, máscaras (telefone, CEP), validação inline, Light/Dark mode e respeito a `prefers-reduced-motion`.

### 7. Qualidade e Automação
- **23 testes automatizados** cobrindo usuários, catálogo, pedidos, avaliações e painel (**89% de cobertura**).
- **Índices de banco** e consultas otimizadas contra N+1.
- **CI no GitHub Actions** (Ruff, `check`, `check --deploy`, `collectstatic` e testes).
- **Comando `seed_demo`** para popular dados de demonstração (apenas com `DEBUG=1`).

---

##  Como Rodar o Projeto

### Opção 1: Inicialização Rápida (Recomendada)

```bash
# 1. Acesse a pasta do projeto e ative o ambiente virtual
cd ~/Downloads/feira_virtual
source .venv/bin/activate        # na 1ª vez: python3 -m venv .venv && pip install -r requirements.txt -r requirements-dev.txt

# 2. Configure o ambiente (1ª vez)
cp .env.example .env

# 3. Prepare o banco e carregue os dados de teste
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py seed_demo

# 4. Inicie o servidor
python manage.py runserver
```

Abra no navegador:
- **Interface da Feira:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Documentação da API (Swagger):** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/) *(exige login de admin ou `ENABLE_SWAGGER=1`)*
- **Painel Administrativo Django:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Healthcheck:** [http://127.0.0.1:8000/api/health/](http://127.0.0.1:8000/api/health/)

---

### Opção 2: Com Banco MySQL Local ou Docker

#### Via Docker Compose (app + MySQL 8.4)
```bash
cp .env.example .env              # defina senhas e DJANGO_SECRET_KEY
docker compose up --build -d
docker compose exec web python manage.py migrate
```

#### Somente o MySQL em container (app rodando local)
```bash
docker compose up db -d
```

#### No MySQL local instalado
```sql
CREATE DATABASE IF NOT EXISTS feira_virtual CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'feira_user'@'%' IDENTIFIED BY 'defina-uma-senha-forte';
GRANT ALL PRIVILEGES ON feira_virtual.* TO 'feira_user'@'%';
FLUSH PRIVILEGES;
```

No `.env`:
```env
DB_ENGINE=mysql
DB_NAME=feira_virtual
DB_USER=feira_user
DB_PASSWORD=defina-uma-senha-forte
DB_HOST=127.0.0.1
DB_PORT=3306
```

Depois execute `python manage.py migrate` e `python manage.py runserver`.

---

### Opção 3: Acesso Externo / Celular (ngrok ou Cloudflare)

1. **Terminal 1:** `python manage.py runserver`
2. **Terminal 2:** `ngrok http 8000`  *(ou `cloudflared tunnel --url http://localhost:8000`)*
3. Abra no celular a URL pública gerada (ex.: `https://xxxx.ngrok-free.app`). O Django já aceita esses domínios em `CSRF_TRUSTED_ORIGINS`.

---

### Checklist de Produção

1. `DJANGO_DEBUG=0` e `DJANGO_SECRET_KEY` aleatória com 50+ caracteres.
2. Restringir `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` ao seu domínio.
3. `DB_ENGINE=mysql` e SMTP real em `EMAIL_*`.
4. Gerar estáticos e validar a segurança:
   ```bash
   python manage.py collectstatic --no-input
   python manage.py check --deploy
   ```
5. Servir com `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3`.
6. Para múltiplas instâncias, mover `/media/` para S3 ou Cloudflare R2 (`django-storages`).

---

## 👥 Contas de Teste (`seed_demo`)

Criadas por `python manage.py seed_demo` (somente com `DJANGO_DEBUG=1`; use `--reset` para recriar):

| Perfil | Usuário | Senha | O que pode fazer |
|---|---|---|---|
| **Cliente** | `cliente_demo` | `cliente-demo-2024` | Carrinho, checkout, Pix, avaliações e reclamações |
| **Produtor** | `produtor_demo` | `produtor-demo-2024` | Gerenciar produtos, aceitar/recusar pedidos e ver vendas |
| **Entregador** | `entregador_demo` | `entregador-demo-2024` | Aceitar e concluir entregas |
| **Administrador** | `admin` | `admin-demo-2024` | Moderação e painel `/admin/` |

> *Dica: no modal de login existem atalhos de preenchimento em 1 clique para essas contas. São credenciais apenas de demonstração — nunca use em produção.*

---

## ⚙️ Variáveis de Ambiente

Todas as opções estão em [`.env.example`](.env.example). As principais:

| Variável | Padrão | Descrição |
|---|---|---|
| `DJANGO_DEBUG` | `0` | `1` apenas em desenvolvimento |
| `DJANGO_SECRET_KEY` | — | Obrigatória quando `DEBUG=0` |
| `DJANGO_ALLOWED_HOSTS` | vazio | Hosts permitidos (separados por vírgula) |
| `DB_ENGINE` | `sqlite` | `sqlite` ou `mysql` (+ `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) |
| `ENABLE_SWAGGER` | `0` | `1` libera `/api/docs/` publicamente |
| `CORS_ALLOW_ALL_ORIGINS` / `CORS_ALLOWED_ORIGINS` | `0` | Origens permitidas |
| `CSRF_TRUSTED_ORIGINS` | localhost + túneis | Origens confiáveis para CSRF |
| `EMAIL_*` | console | Envio de e-mail (SMTP em produção) |
| `THROTTLE_*` | ver `.env.example` | Limites de requisições (geral, login, registro, recuperação de senha) |
| `PIX_WEBHOOK_SECRET` | dev | Segredo HMAC do webhook Pix |

---

## 📦 Estrutura dos Módulos

```
feira_virtual/
├── config/        # Configurações, URLs, middleware de CSP e validadores de upload
├── usuarios/      # Usuários (4 perfis), endereços, autenticação JWT, LGPD e seed_demo
├── catalogo/      # Categorias, produtos, vitrine de produtores e estatísticas
├── pedidos/       # Carrinho, checkout, máquina de estados, notificações e Pix
├── avaliacoes/    # Avaliações de produtos/produtores e reclamações
├── painel/        # Moderação administrativa, indicadores e log de auditoria
├── frontend/      # index.html, style.css, main.js, js/ (módulos ES) e assets/ (logos, favicons, PWA)
├── Dockerfile · docker-compose.yml · requirements.txt · requirements-dev.txt
└── .github/workflows/ci.yml
```

---

##  Principais Endpoints da API

### Autenticação, Perfil e LGPD
- `POST /api/auth/login/` — Retorna tokens JWT (`access` e `refresh`).
- `POST /api/auth/refresh/` · `POST /api/auth/logout/` — Renova o token / encerra a sessão.
- `POST /api/auth/registro/cliente/` · `/produtor/` · `/entregador/` — Cadastros por perfil.
- `POST /api/auth/recuperar-senha/` · `POST /api/auth/redefinir-senha/` — Recuperação de senha.
- `GET/PATCH /api/perfil/` — Dados da conta; `perfil/produtor/` e `perfil/entregador/` para dados profissionais.
- `GET /api/perfil/exportar-dados/` · `DELETE /api/perfil/excluir-conta/` — Direitos LGPD.
- `CRUD /api/enderecos/` — Endereços de entrega.

### Catálogo
- `GET /api/categorias/` — Categorias ativas.
- `GET /api/produtos/` — Produtos públicos (`?search=`, `?categoria=`, `?tipo_producao=`, `?produtor=`, `?ordering=`, `?page=`).
- `GET /api/produtores/` — Vitrine de produtores aprovados.
- `GET /api/estatisticas/` — Números reais da feira (famílias atendidas na semana, produtores, produtos).
- `CRUD /api/produtor/produtos/` — Produtos do próprio produtor (com upload de foto).

### Carrinho, Pedidos e Pix
- `GET/DELETE /api/carrinho/` · `POST/PATCH/DELETE /api/carrinho/itens/` — Carrinho.
- `POST /api/pedidos/` — Finaliza o carrinho (um pedido por produtor); `GET /api/pedidos/` lista o histórico.
- `POST /api/pedidos/{id}/cancelar/` — Cancelamento pelo cliente.
- `GET /api/pedidos/{id}/pix/` — Cobrança Pix (QR Code e copia-e-cola).
- `POST /api/pedidos/pix/webhook/` — Confirmação de pagamento (assinatura HMAC).

### Produtor e Entregador
- `GET /api/produtor/pedidos/` · `POST .../{id}/aceitar/` · `.../recusar/` · `.../status/` · `GET .../vendas/`
- `GET /api/produtor/avaliacoes/` — Avaliações recebidas.
- `GET /api/entregas/?escopo=disponiveis|minhas` · `POST .../{id}/aceitar/` · `.../saiu-para-entrega/` · `.../confirmar/`

### Avaliações, Administração e Sistema
- `GET/POST /api/avaliacoes/` · `GET/POST /api/reclamacoes/`
- `GET /api/admin/indicadores/` e gestão em `/api/admin/{usuarios,produtores,produtos,pedidos,reclamacoes}/`
- `GET /api/health/` — Saúde da aplicação e do banco.

---

## ⚖️ Fluxo de Pedido e Regras de Negócio

```text
PENDENTE ─▶ ACEITO ─▶ EM_PREPARO ─▶ PRONTO ─▶ EM_ENTREGA ─▶ CONCLUIDO
   │          │            │           └──(retirada)────────▶ CONCLUIDO
   ├─▶ RECUSADO (produtor)
   └──────────────(cliente cancela, estoque devolvido)─────▶ CANCELADO
```

1. **Separação por Produtor:** o carrinho pode ter itens de produtores distintos; no checkout, a compra é dividida em um pedido independente para cada produtor.
2. **Controle Estrito de Estoque:** validado ao adicionar ao carrinho e no checkout (com lock). A baixa efetiva ocorre quando o produtor **aceita** o pedido; cancelamento ou recusa devolvem o estoque de forma transacional.
3. **Moderação de Produtores:** novos produtores iniciam como `PENDENTE`; seus produtos só aparecem no catálogo após aprovação do administrador.
4. **Formas de Pagamento Dinâmicas:** cada produtor define o que aceita (Pix, cartão com maquininha própria ou dinheiro); o checkout bloqueia opções incompatíveis.
5. **Avaliações Confiáveis:** só quem teve pedido concluído avalia, uma única vez por item.
6. **Histórico Imutável:** preços unitários e nomes são copiados para `ItemPedido`, preservando pedidos passados.
7. **Privacidade:** a chave Pix do produtor não aparece na vitrine pública nem em pedidos cancelados/recusados.

---

## 🎨 Design System e Identidade Visual

- **Paleta (regra 60-30-10, contraste WCAG 2.1 AA):**

  | Token | Cor | Uso |
  |---|---|---|
  | `--color-primary` | `#246F11` | Verde principal — cabeçalho, estrutura e identidade (30%) |
  | `--color-primary-dark` | `#1B4312` | Hover e alto contraste |
  | `--color-primary-light` | `#67AE25` | Realces |
  | `--color-cta` | `#F7990C` | Laranja restrito a botões de ação e foco (10%) |
  | Fundos neutros | `#FAFAF8` (claro) / `#141712` (escuro) | Base da interface (60%) |

- **Light e Dark Mode:** alternância com 1 clique, preferência salva no `localStorage`; a logo troca automaticamente de variante.
- **Tipografia:** `Inter` (interface) e `Fraunces` (títulos) com *fallback* para fontes do sistema — sem requisições externas, compatível com a CSP.
- **Componentes:** carrinho lateral (Drawer), modais acessíveis com foco preso, toasts assíncronos, badges de status, skeleton loading e timeline de pedido.
- **Tokens CSS:** variáveis centralizadas no topo de `frontend/style.css`.
- **Assets:** logos (PNG/WebP), favicons, ícones PWA e `og-image` em `frontend/assets/`.


## 🧪 Testes e CI

```bash
python manage.py test                                  # 23 testes
coverage run manage.py test && coverage report         # cobertura atual: 89%
python manage.py check --deploy                        # com DEBUG=0 e SECRET_KEY definida
python manage.py spectacular --validate > /dev/null    # valida o schema OpenAPI
```

O GitHub Actions (`.github/workflows/ci.yml`) executa Ruff, `check`, `check --deploy`, `collectstatic` e testes com cobertura a cada push/PR na `main`.

---

## 🔮 Próximos Passos

- Integrar gateway Pix real (Mercado Pago / Efí / Asaas) e WhatsApp oficial.
- Migrar os tokens JWT do `localStorage` para cookies `httpOnly`.
- Self-host das fontes Inter/Fraunces (`.woff2`) e auditoria Lighthouse.
- Cálculo automático de frete por CEP e armazenamento de mídia em S3/Cloudflare R2.
- Build da imagem Docker no CI.
