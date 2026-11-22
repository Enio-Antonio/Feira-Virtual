"""
Comando de demonstração: popula o banco com dados realistas do Rio Grande do Norte (RN).
Só pode rodar com DEBUG=True (nunca em produção).

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # remove dados do seed e recria tudo
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Popula o banco com produtores, clientes, entregadores, produtos, pedidos e avaliações do RN (só com DEBUG=1)"

    SEED_CATEGORIES = [
        ("Hortaliças", "Folhosas e temperos colhidos no dia por hortas familiares do RN."),
        ("Frutas", "Frutas tropicais e da estação direto dos pomares potiguares."),
        ("Legumes e Raízes", "Legumes frescos e raízes cultivados na agricultura familiar."),
        ("Ovos e Laticínios", "Ovos caipiras, queijos de coalho e manteiga artesanal do Seridó."),
        ("Mel e Artesanais", "Méis nativos de abelha tiúba/jandaíra, doces e conservas artesanais."),
        ("Grãos e Farinhas", "Feijão verde, feijão macassar, farinha de mandioca e grãos regionais."),
    ]

    LEGACY_DEMO_CATEGORIES = [
        "Grãos e Cereais",
        "Verduras e Legumes",
    ]

    SEED_USERNAMES = [
        # Contas principais de demonstração (1 por perfil)
        "admin",
        "cliente_demo",
        "produtor_demo",
        "entregador_demo",
        # Clientes adicionais (RN)
        "ana_beatriz",
        "lucas_bezerra",
        "fernanda_lima",
        "rafael_costa",
        # Produtores adicionais (RN)
        "sitio_esperanca",
        "prod_valeverde",
        "prod_serido",
        "prod_cearamirim",
        "prod_mossoro",
        "prod_pendente_rn",
        # Entregadores adicionais (RN)
        "ent_thiago",
        "ent_juliana",
    ]

    SEED_LEGACY_EMAILS = [
        "admin@demo.com",
        "cliente@demo.com",
        "produtor@demo.com",
        "entregador@demo.com",
        "esperanca@feira.com",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove dados anteriores do seed (preservando contas pessoais fora do seed) antes de recriar",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo só pode rodar com DEBUG=1. "
                "Nunca execute em produção."
            )

        self.stdout.write(self.style.WARNING("⚠  Rodando seed_demo (dados realistas do RN) em modo DEBUG …"))

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            resumo = self._seed()

        self.stdout.write(self.style.SUCCESS("Seed do Rio Grande do Norte concluído com sucesso!"))
        self.stdout.write("")
        self.stdout.write(
            f"Resumo: {resumo['produtores']} produtores RN ({resumo['produtores_pendentes']} pendente) · "
            f"{resumo['produtos']} produtos · {resumo['clientes']} clientes · "
            f"{resumo['entregadores']} entregadores · {resumo['pedidos']} pedidos · "
            f"{resumo['avaliacoes']} avaliações · {resumo['reclamacoes']} reclamações"
        )
        self.stdout.write("")
        self.stdout.write("Contas principais para demonstração (use o usuário / senha no login):")
        self.stdout.write("  Admin      → admin / admin-demo-2024")
        self.stdout.write("  Cliente    → cliente_demo / cliente-demo-2024        (Maria Eduarda Nogueira — Natal/RN)")
        self.stdout.write("  Produtor   → produtor_demo / produtor-demo-2024      (Sítio Serra Verde — Macaíba/RN)")
        self.stdout.write("  Entregador → entregador_demo / entregador-demo-2024  (Carlos Eduardo — Grande Natal/RN)")
        self.stdout.write("")
        self.stdout.write("Demais contas RN criadas (senha padrão: feira-rn-2024):")
        self.stdout.write("  Clientes     → ana_beatriz, lucas_bezerra, fernanda_lima, rafael_costa")
        self.stdout.write("  Produtores   → sitio_esperanca, prod_valeverde, prod_serido, prod_cearamirim, prod_mossoro, prod_pendente_rn")
        self.stdout.write("  Entregadores → ent_thiago, ent_juliana")

    # ------------------------------------------------------------------ #

    def _reset(self):
        """Remove apenas os dados criados pelo seed (e resquícios [DEMO]), preservando contas externas."""
        from django.db.models import ProtectedError, Q

        from avaliacoes.models import Avaliacao, AvaliacaoCliente, Reclamacao
        from catalogo.models import Categoria, Produto
        from painel.models import LogAuditoria
        from pedidos.models import Carrinho, Pedido
        from usuarios.models import Endereco, Usuario

        self.stdout.write("  Removendo dados anteriores do seed …")
        users_qs = Usuario.objects.filter(
            Q(username__in=self.SEED_USERNAMES) | Q(email__in=self.SEED_LEGACY_EMAILS)
        )
        user_ids = list(users_qs.values_list("id", flat=True))

        pedidos_qs = Pedido.objects.filter(
            Q(numero_publico__startswith="PED-RN")
            | Q(cliente_id__in=user_ids)
            | Q(produtor__usuario_id__in=user_ids)
        )
        pedido_ids = list(pedidos_qs.values_list("id", flat=True))

        Avaliacao.objects.filter(
            Q(pedido_id__in=pedido_ids)
            | Q(cliente_id__in=user_ids)
            | Q(produtor__usuario_id__in=user_ids)
        ).delete()
        AvaliacaoCliente.objects.filter(
            Q(pedido_id__in=pedido_ids)
            | Q(cliente_id__in=user_ids)
            | Q(produtor__usuario_id__in=user_ids)
        ).delete()
        Reclamacao.objects.filter(
            Q(pedido_id__in=pedido_ids) | Q(cliente_id__in=user_ids)
        ).delete()
        LogAuditoria.objects.filter(usuario_id__in=user_ids).delete()
        pedidos_qs.delete()
        Carrinho.objects.filter(cliente_id__in=user_ids).delete()
        Endereco.objects.filter(usuario_id__in=user_ids).delete()
        Produto.objects.filter(produtor__usuario_id__in=user_ids).delete()
        users_qs.delete()

        cat_nomes = [nome for nome, _ in self.SEED_CATEGORIES] + self.LEGACY_DEMO_CATEGORIES
        for cat in Categoria.objects.filter(Q(nome__startswith="[DEMO]") | Q(nome__in=cat_nomes)):
            try:
                cat.delete()
            except ProtectedError:
                pass

    # ------------------------------------------------------------------ #

    def _upsert_user(self, username, email, first_name, last_name, tipo, password, telefone="", is_staff=False, is_superuser=False):
        from usuarios.models import Usuario

        user = Usuario.objects.filter(username=username).first() or Usuario.objects.filter(email=email).first()
        if user is None:
            user = Usuario(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                tipo=tipo,
                telefone=telefone,
                is_staff=is_staff,
                is_superuser=is_superuser,
                is_active=True,
            )
            user.set_password(password)
            user.save()
        else:
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.tipo = tipo
            user.telefone = telefone
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.excluido_em = None
            if not user.has_usable_password():
                user.set_password(password)
            user.save()
        return user

    def _seed(self):
        from avaliacoes.models import Avaliacao, AvaliacaoCliente, Reclamacao
        from catalogo.models import Categoria, Produto
        from painel.models import LogAuditoria
        from pedidos.models import HistoricoStatus, ItemPedido, Pedido
        from usuarios.models import Endereco, PerfilEntregador, PerfilProdutor, Usuario

        agora = timezone.now()

        # ── 1. Superusuário Administrador ───────────────────────────────
        admin = self._upsert_user(
            username="admin",
            email="admin@demo.com",
            first_name="Admin",
            last_name="Feira Virtual",
            tipo=Usuario.Tipo.ADMIN,
            password="admin-demo-2024",
            telefone="(84) 99900-1000",
            is_staff=True,
            is_superuser=True,
        )
        self._ok("Administrador (admin)")

        # ── 2. Clientes do RN e Endereços ───────────────────────────────
        clientes_spec = [
            (
                "cliente_demo", "cliente@demo.com", "Maria Eduarda", "Nogueira",
                "cliente-demo-2024", "(84) 99812-3401",
                [
                    ("Casa", "59056-000", "Av. Prudente de Morais", "2410", "Apto 502", "Lagoa Nova", "Natal", "RN"),
                    ("Trabalho", "59090-001", "Av. Engenheiro Roberto Freire", "3120", "Sala 14", "Ponta Negra", "Natal", "RN"),
                ],
            ),
            (
                "ana_beatriz", "ana.beatriz@feirarn.com", "Ana Beatriz", "Fernandes",
                "feira-rn-2024", "(84) 99645-1208",
                [("Casa", "59020-400", "Rua Ângelo Varela", "1185", "Bloco B", "Tirol", "Natal", "RN")],
            ),
            (
                "lucas_bezerra", "lucas.bezerra@feirarn.com", "Lucas", "Bezerra Dantas",
                "feira-rn-2024", "(84) 99923-7845",
                [("Casa", "59082-095", "Rua Walter Duarte Pereira", "420", "Casa 03", "Capim Macio", "Natal", "RN")],
            ),
            (
                "fernanda_lima", "fernanda.lima@feirarn.com", "Fernanda", "Soares de Lima",
                "feira-rn-2024", "(84) 99411-5520",
                [("Casa", "59151-250", "Av. Abel Cabral", "1680", "Cond. Jardins, Casa 12", "Nova Parnamirim", "Parnamirim", "RN")],
            ),
            (
                "rafael_costa", "rafael.costa@feirarn.com", "Rafael Henrique", "Costa",
                "feira-rn-2024", "(84) 99187-6632",
                [("Casa", "59012-300", "Rua Seridó", "512", "Apto 801", "Petrópolis", "Natal", "RN")],
            ),
        ]
        clientes = {}
        enderecos_principais = {}
        for uname, email, fn, ln, pwd, tel, ends in clientes_spec:
            u = self._upsert_user(uname, email, fn, ln, Usuario.Tipo.CLIENTE, pwd, telefone=tel)
            clientes[uname] = u
            for idx, (rot, cep, log, num, comp, bai, cid, est) in enumerate(ends):
                end, _ = Endereco.objects.update_or_create(
                    usuario=u,
                    rotulo=rot,
                    defaults={
                        "cep": cep,
                        "logradouro": log,
                        "numero": num,
                        "complemento": comp,
                        "bairro": bai,
                        "cidade": cid,
                        "estado": est,
                    },
                )
                if idx == 0:
                    enderecos_principais[uname] = end
        self._ok(f"{len(clientes)} clientes potiguares com endereços no RN")

        # ── 3. Produtores Rurais do RN (6 aprovados + 1 pendente) ───────
        produtores_spec = [
            (
                "produtor_demo", "produtor@demo.com", "João Batista", "Medeiros",
                "produtor-demo-2024", "(84) 99844-1122",
                {
                    "nome_propriedade": "Sítio Serra Verde",
                    "descricao": "Agricultura familiar agroecológica em Macaíba há 18 anos, com colheita diária de hortaliças, legumes e mel de abelha nativa.",
                    "endereco_propriedade": "Estrada de Cajazeiras, km 6 — Zona Rural",
                    "cidade": "Macaíba",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "serraverde.rn@pix.com",
                    "possui_maquininha": True,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "sitio_esperanca", "esperanca@feira.com", "Maria", "Ferreira de Souza",
                "feira-rn-2024", "(84) 99710-3344",
                {
                    "nome_propriedade": "Sítio Esperança",
                    "descricao": "Cultivo familiar sustentável na Grande Natal com foco em folhas hidropônicas, tomates agroecológicos e mel puro de abelha tiúba.",
                    "endereco_propriedade": "Estrada da Redinha Nova, Lote 14",
                    "cidade": "Natal",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "sitioesperanca.rn@pix.com",
                    "possui_maquininha": False,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "prod_valeverde", "valeverde@feirarn.com", "Antônia Francisca", "da Costa",
                "feira-rn-2024", "(84) 99612-8877",
                {
                    "nome_propriedade": "Chácara Vale Verde",
                    "descricao": "Pomar familiar em Nísia Floresta especializado em frutas tropicais colhidas no ponto certo, sem agrotóxicos.",
                    "endereco_propriedade": "Comunidade de Mazapas, RN-063, km 9",
                    "cidade": "Nísia Floresta",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "chacaravaleverde@pix.com",
                    "possui_maquininha": True,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "prod_serido", "serido@feirarn.com", "Manoel Severino", "de Araújo",
                "feira-rn-2024", "(84) 99933-4510",
                {
                    "nome_propriedade": "Fazenda Sabores do Seridó",
                    "descricao": "Produção artesanal do Seridó potiguar: queijo de coalho, manteiga da terra, ovos caipiras de galinhas criadas soltas e mel de jandaíra.",
                    "endereco_propriedade": "Sítio Barra da Espingarda, Zona Rural",
                    "cidade": "Caicó",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "saboresdoserido@pix.com",
                    "possui_maquininha": True,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "prod_cearamirim", "cearamirim@feirarn.com", "Raimunda Nonata", "Pereira",
                "feira-rn-2024", "(84) 99488-7711",
                {
                    "nome_propriedade": "Horta Agroecológica do Vale",
                    "descricao": "Horta comunitária familiar no Vale do Ceará-Mirim produzindo verduras orgânicas, cheiro-verde e raízes frescas.",
                    "endereco_propriedade": "Assentamento Rosário, Estrada do Vale km 4",
                    "cidade": "Ceará-Mirim",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "hortavale.rn@pix.com",
                    "possui_maquininha": False,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "prod_mossoro", "mossoro@feirarn.com", "Francisco das Chagas", "Oliveira",
                "feira-rn-2024", "(84) 99805-6090",
                {
                    "nome_propriedade": "Sítio Sol Nascente",
                    "descricao": "Fruticultura e grãos da agricultura familiar do Oeste Potiguar: melão amarelo, melancia doce, feijão verde e jerimum caboclo.",
                    "endereco_propriedade": "Comunidade Maísa, BR-304, km 22",
                    "cidade": "Mossoró",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.APROVADO,
                    "chave_pix": "sitiosolnascente.rn@pix.com",
                    "possui_maquininha": True,
                    "aceita_dinheiro": True,
                },
            ),
            (
                "prod_pendente_rn", "riachodoce@feirarn.com", "Luzia", "Bezerra Lima",
                "feira-rn-2024", "(84) 99520-1988",
                {
                    "nome_propriedade": "Sítio Riacho Doce",
                    "descricao": "Pequena propriedade familiar em São José de Mipibu voltada para farinha de mandioca artesanal, goma fresca e bolos regionais.",
                    "endereco_propriedade": "Comunidade Pau Brasil, Zona Rural",
                    "cidade": "São José de Mipibu",
                    "estado": "RN",
                    "status": PerfilProdutor.Status.PENDENTE,
                    "chave_pix": "riachodoce.rn@pix.com",
                    "possui_maquininha": False,
                    "aceita_dinheiro": True,
                },
            ),
        ]
        perfis_produtores = {}
        for uname, email, fn, ln, pwd, tel, dados_perfil in produtores_spec:
            u = self._upsert_user(uname, email, fn, ln, Usuario.Tipo.PRODUTOR, pwd, telefone=tel)
            perfil, _ = PerfilProdutor.objects.update_or_create(
                usuario=u,
                defaults={**dados_perfil, "excluido_em": None},
            )
            perfis_produtores[uname] = perfil
        self._ok(f"{len(perfis_produtores)} produtores rurais do RN (6 aprovados + 1 pendente)")

        # ── 4. Entregadores do RN ───────────────────────────────────────
        entregadores_spec = [
            (
                "entregador_demo", "entregador@demo.com", "Carlos Eduardo", "Nascimento",
                "entregador-demo-2024", "(84) 99877-2210",
                "Moto Honda CG 160", "RNP4E21", "Natal, Parnamirim e Macaíba/RN",
            ),
            (
                "ent_thiago", "thiago.entregas@feirarn.com", "Thiago", "Barbosa de Souza",
                "feira-rn-2024", "(84) 99734-9012",
                "Fiat Fiorino Baú", "QGA7B89", "Grande Natal e Região Metropolitana/RN",
            ),
            (
                "ent_juliana", "juliana.entregas@feirarn.com", "Juliana Kelly", "Medeiros",
                "feira-rn-2024", "(84) 99205-4488",
                "Moto Yamaha Factor 150", "RNM2C45", "Zona Sul de Natal e Parnamirim/RN",
            ),
        ]
        entregadores = {}
        for uname, email, fn, ln, pwd, tel, veiculo, placa, area in entregadores_spec:
            u = self._upsert_user(uname, email, fn, ln, Usuario.Tipo.ENTREGADOR, pwd, telefone=tel)
            PerfilEntregador.objects.update_or_create(
                usuario=u,
                defaults={"veiculo": veiculo, "placa": placa, "area_atuacao": area},
            )
            entregadores[uname] = u
        self._ok(f"{len(entregadores)} entregadores parceiros do RN")

        # ── 5. Categorias limpas (sem prefixo [DEMO]) ───────────────────
        cats = {}
        for nome, desc in self.SEED_CATEGORIES:
            cat, _ = Categoria.objects.update_or_create(
                nome=nome,
                defaults={"descricao": desc, "ativa": True},
            )
            cats[nome] = cat
        self._ok(f"{len(cats)} categorias ativas")

        # ── 6. Produtos dos produtores do RN (30 públicos + 2 pendente) ─
        U = Produto.Unidade
        TP = Produto.TipoProducao
        produtos_spec = [
            # Sítio Serra Verde (produtor_demo — Macaíba/RN)
            ("produtor_demo", "Alface Crespa Orgânica", "Hortaliças", "3.50", "45", U.MACO, TP.ORGANICO_CERTIFICADO,
             "Alface crespa colhida na madrugada em Macaíba, folhas crocantes e livres de agrotóxicos."),
            ("produtor_demo", "Tomate Cereja Agroecológico", "Legumes e Raízes", "9.50", "28", U.KG, TP.AGROECOLOGICO,
             "Tomates cereja doces e firmes, ideais para saladas e molhos frescos."),
            ("produtor_demo", "Cheiro-Verde Fresco (Coentro e Cebolinha)", "Hortaliças", "2.50", "60", U.MACO, TP.ORGANICO_CERTIFICADO,
             "Maço generoso de coentro e cebolinha da agricultura familiar potiguar."),
            ("produtor_demo", "Cenoura Orgânica da Terra", "Legumes e Raízes", "6.20", "32", U.KG, TP.ORGANICO_CERTIFICADO,
             "Cenouras selecionadas, adocicadas e cultivadas em solo adubado organicamente."),
            ("produtor_demo", "Mel de Abelha Jandaíra (300 ml)", "Mel e Artesanais", "34.00", "4", U.UNIDADE, TP.AGROECOLOGICO,
             "Mel nativo do Nordeste produzido por abelhas sem ferrão; sabor suave e floral (estoque limitado)."),
            ("produtor_demo", "Batata-Doce Roxa", "Legumes e Raízes", "5.40", "40", U.KG, TP.AGROECOLOGICO,
             "Batata-doce roxa de polpa macia, colhida semanalmente em Macaíba."),

            # Sítio Esperança (sitio_esperanca — Natal/RN)
            ("sitio_esperanca", "Alface Crespa Hidropônica", "Hortaliças", "3.80", "50", U.MACO, TP.ORGANICO_CERTIFICADO,
             "Alface hidropônica limpa e pronta para o consumo, produzida na Grande Natal."),
            ("sitio_esperanca", "Rúcula Selvagem", "Hortaliças", "4.20", "24", U.MACO, TP.ORGANICO_CERTIFICADO,
             "Folhas frescas de rúcula com sabor marcante, colhidas no dia da entrega."),
            ("sitio_esperanca", "Tomate Italiano Agroecológico", "Legumes e Raízes", "7.80", "30", U.KG, TP.AGROECOLOGICO,
             "Tomate italiano carnudo com baixa acidez, excelente para molhos caseiros."),
            ("sitio_esperanca", "Banana Prata Climatizada", "Frutas", "6.50", "42", U.KG, TP.CONVENCIONAL,
             "Banana prata selecionada direto do produtor, doce e firme."),
            ("sitio_esperanca", "Mel Puro de Abelha Tiúba", "Mel e Artesanais", "28.00", "16", U.UNIDADE, TP.AGROECOLOGICO,
             "Mel puro artesanal envasado em pote de vidro de 500 g."),
            ("sitio_esperanca", "Pepino Japonês Fresco", "Legumes e Raízes", "5.90", "22", U.KG, TP.AGROECOLOGICO,
             "Pepino crocante de casca fina, colhido diariamente."),

            # Chácara Vale Verde (prod_valeverde — Nísia Floresta/RN)
            ("prod_valeverde", "Caju Vermelho da Safra", "Frutas", "8.90", "35", U.KG, TP.AGROECOLOGICO,
             "Cajus suculentos e aromáticos colhidos nos cajueiros de Nísia Floresta."),
            ("prod_valeverde", "Manga Rosa Madura", "Frutas", "7.40", "48", U.KG, TP.AGROECOLOGICO,
             "Manga rosa doce e perfumada, colhida no pé na semana da feira."),
            ("prod_valeverde", "Maracujá Azedo para Suco", "Frutas", "9.80", "26", U.KG, TP.CONVENCIONAL,
             "Maracujás pesados e cheios de polpa, ideais para sucos e sobremesas."),
            ("prod_valeverde", "Mamão Formosa", "Frutas", "5.50", "30", U.KG, TP.AGROECOLOGICO,
             "Mamão formosa de polpa alaranjada intensa e sabor adocicado."),
            ("prod_valeverde", "Goiaba Vermelha Paluma", "Frutas", "6.80", "34", U.KG, TP.ORGANICO_CERTIFICADO,
             "Goiabas vermelhas orgânicas de Nísia Floresta, perfeitas in natura ou em doces."),

            # Fazenda Sabores do Seridó (prod_serido — Caicó/RN)
            ("prod_serido", "Queijo de Coalho Artesanal de Caicó", "Ovos e Laticínios", "38.00", "25", U.KG, TP.AGROECOLOGICO,
             "Tradicional queijo de coalho do Seridó, não derrete na brasa e tem cura equilibrada."),
            ("prod_serido", "Manteiga da Terra (Garrafa 500 ml)", "Ovos e Laticínios", "26.50", "18", U.UNIDADE, TP.AGROECOLOGICO,
             "Manteiga de garrafa pura e aromática feita artesanalmente em Caicó/RN."),
            ("prod_serido", "Ovos Caipiras (Dúzia)", "Ovos e Laticínios", "13.50", "55", U.UNIDADE, TP.AGROECOLOGICO,
             "Ovos de galinhas criadas soltas com alimentação natural e gema bem alaranjada."),
            ("prod_serido", "Doce de Leite Artesanal (400 g)", "Mel e Artesanais", "18.90", "20", U.UNIDADE, TP.CONVENCIONAL,
             "Doce de leite pastoso cozido em tacho de cobre no interior do RN."),
            ("prod_serido", "Nata Fresca do Seridó (300 g)", "Ovos e Laticínios", "14.00", "14", U.UNIDADE, TP.AGROECOLOGICO,
             "Nata cremosa fresca ideal para cuscuz, macaxeira e tapioca."),

            # Horta Agroecológica do Vale (prod_cearamirim — Ceará-Mirim/RN)
            ("prod_cearamirim", "Macaxeira Descascada a Vácuo", "Legumes e Raízes", "7.50", "38", U.KG, TP.AGROECOLOGICO,
             "Macaxeira manteiga do Vale do Ceará-Mirim, cozinha rápido e desmancha na boca."),
            ("prod_cearamirim", "Couve-Folha Orgânica", "Hortaliças", "3.20", "40", U.MACO, TP.ORGANICO_CERTIFICADO,
             "Folhas tenras de couve orgânica, perfeitas para sucos verdes e refogados."),
            ("prod_cearamirim", "Alface Americana Orgânica", "Hortaliças", "4.50", "30", U.UNIDADE, TP.ORGANICO_CERTIFICADO,
             "Cabeça firme e crocante de alface americana certificada."),
            ("prod_cearamirim", "Pimentão Verde Agroecológico", "Legumes e Raízes", "6.40", "25", U.KG, TP.AGROECOLOGICO,
             "Pimentões frescos cultivados sem pesticidas sintéticos."),

            # Sítio Sol Nascente (prod_mossoro — Mossoró/RN)
            ("prod_mossoro", "Melão Amarelo de Mossoró", "Frutas", "6.20", "50", U.KG, TP.CONVENCIONAL,
             "Melão amarelo de alto teor de doçura cultivado no polo agrícola de Mossoró/RN."),
            ("prod_mossoro", "Feijão Verde Debulhado", "Grãos e Farinhas", "14.50", "35", U.KG, TP.AGROECOLOGICO,
             "Feijão verde fresco já debulhado, pronto para preparar baião de dois e refogados."),
            ("prod_mossoro", "Jerimum Caboclo (Fatia / Kg)", "Legumes e Raízes", "4.80", "45", U.KG, TP.AGROECOLOGICO,
             "Jerimum caboclo enxuto e adocicado, excelente para sopas e acompanhamentos."),
            ("prod_mossoro", "Farinha de Mandioca Torrada (1 kg)", "Grãos e Farinhas", "8.50", "40", U.KG, TP.CONVENCIONAL,
             "Farinha branca fina torrada em casa de farinha tradicional do interior potiguar."),

            # Sítio Riacho Doce (prod_pendente_rn — São José de Mipibu/RN — PENDENTE de aprovação admin)
            ("prod_pendente_rn", "Goma de Tapioca Hidratada (1 kg)", "Grãos e Farinhas", "9.00", "30", U.KG, TP.AGROECOLOGICO,
             "Goma fresca peneirada pronta para frigideira, produzida em São José de Mipibu."),
            ("prod_pendente_rn", "Feijão Macassar Seco (1 kg)", "Grãos e Farinhas", "10.50", "25", U.KG, TP.CONVENCIONAL,
             "Feijão macassar selecionado da agricultura familiar potiguar."),
        ]

        produtos_map = {}
        for prod_uname, nome, cat_nome, preco, est, un, tp, desc in produtos_spec:
            prod_obj, _ = Produto.objects.update_or_create(
                nome=nome,
                produtor=perfis_produtores[prod_uname],
                defaults={
                    "categoria": cats[cat_nome],
                    "descricao": desc,
                    "preco": Decimal(preco),
                    "estoque": Decimal(est),
                    "unidade_medida": un,
                    "tipo_producao": tp,
                    "ativo": True,
                    "oculto_moderacao": False,
                    "excluido_em": None,
                },
            )
            produtos_map[(prod_uname, nome)] = prod_obj
        self._ok(f"{len(produtos_map)} produtos regionais do RN cadastrados")

        # ── 7. Pedidos realistas (últimos 6 dias — cobrindo todos os fluxos) ─
        S = Pedido.Status
        M = Pedido.Modalidade
        FP = Pedido.FormaPagamento

        def _criar_pedido(
            numero,
            cliente_uname,
            prod_uname,
            status_final,
            modalidade,
            forma_pag,
            itens_lista,
            dias_atras,
            entregador_uname=None,
            taxa="0.00",
            observacao="",
            motivo="",
            previsao="",
            historico_steps=None,
        ):
            cliente_u = clientes[cliente_uname]
            perfil_p = perfis_produtores[prod_uname]
            ent_u = entregadores[entregador_uname] if entregador_uname else None
            end_txt = enderecos_principais[cliente_uname].como_texto() if modalidade == M.ENTREGA else ""
            taxa_dec = Decimal(taxa) if modalidade == M.ENTREGA else Decimal("0.00")
            est_baixado = status_final in (S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO)

            pedido, created = Pedido.objects.get_or_create(
                numero_publico=numero,
                defaults={
                    "cliente": cliente_u,
                    "produtor": perfil_p,
                    "entregador": ent_u,
                    "status": status_final,
                    "modalidade": modalidade,
                    "forma_pagamento": forma_pag,
                    "endereco_entrega": end_txt,
                    "observacao": observacao,
                    "taxa_entrega": taxa_dec,
                    "previsao_entrega": previsao,
                    "motivo_cancelamento": motivo,
                    "estoque_baixado": est_baixado,
                },
            )
            if not created:
                return pedido

            total = Decimal("0.00")
            for nome_prod, qtd in itens_lista:
                p_obj = produtos_map[(prod_uname, nome_prod)]
                qtd_dec = Decimal(str(qtd))
                ip = ItemPedido.objects.create(
                    pedido=pedido,
                    produto=p_obj,
                    nome_produto=p_obj.nome,
                    unidade_medida=p_obj.unidade_medida,
                    preco_unitario=p_obj.preco,
                    quantidade=qtd_dec,
                )
                total += ip.subtotal
            pedido.total = total
            pedido.save(update_fields=["total"])

            dt_base = agora - timedelta(days=dias_atras, hours=2)
            Pedido.objects.filter(pk=pedido.pk).update(criado_em=dt_base, atualizado_em=dt_base + timedelta(hours=2))

            steps = historico_steps or [S.PENDENTE]
            for i, st in enumerate(steps):
                hs = HistoricoStatus.objects.create(pedido=pedido, status=st)
                HistoricoStatus.objects.filter(pk=hs.pk).update(criado_em=dt_base + timedelta(minutes=25 * i))
            return pedido

        pedidos_map = {}

        # ── 9 Pedidos CONCLUIDO (faturamento, ganhos de entrega, estatísticas da semana) ──
        pedidos_map["PED-RN000001"] = _criar_pedido(
            "PED-RN000001", "cliente_demo", "produtor_demo", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Alface Crespa Orgânica", 2), ("Tomate Cereja Agroecológico", "1.500"), ("Mel de Abelha Jandaíra (300 ml)", 1)],
            dias_atras=5, entregador_uname="entregador_demo", taxa="7.50",
            observacao="Por favor, avisar na portaria ao chegar.",
            previsao="Entregue no mesmo dia",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000002"] = _criar_pedido(
            "PED-RN000002", "ana_beatriz", "prod_serido", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Queijo de Coalho Artesanal de Caicó", "1.000"), ("Manteiga da Terra (Garrafa 500 ml)", 1), ("Ovos Caipiras (Dúzia)", 2)],
            dias_atras=4, entregador_uname="entregador_demo", taxa="8.00",
            observacao="Queijo bem fresquinho se possível.",
            previsao="Entrega matinal",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000003"] = _criar_pedido(
            "PED-RN000003", "lucas_bezerra", "prod_valeverde", S.CONCLUIDO, M.ENTREGA, FP.CARTAO,
            [("Caju Vermelho da Safra", "2.000"), ("Manga Rosa Madura", "1.500"), ("Goiaba Vermelha Paluma", "1.000")],
            dias_atras=4, entregador_uname="entregador_demo", taxa="7.00",
            previsao="Tarde (14h às 17h)",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000004"] = _criar_pedido(
            "PED-RN000004", "fernanda_lima", "sitio_esperanca", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Alface Crespa Hidropônica", 3), ("Rúcula Selvagem", 2), ("Mel Puro de Abelha Tiúba", 1)],
            dias_atras=3, entregador_uname="entregador_demo", taxa="8.50",
            observacao="Deixar com a portaria do condomínio.",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000005"] = _criar_pedido(
            "PED-RN000005", "rafael_costa", "prod_mossoro", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Melão Amarelo de Mossoró", "2.500"), ("Feijão Verde Debulhado", "1.500"), ("Farinha de Mandioca Torrada (1 kg)", "1.000")],
            dias_atras=3, entregador_uname="entregador_demo", taxa="7.50",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000006"] = _criar_pedido(
            "PED-RN000006", "ana_beatriz", "produtor_demo", S.CONCLUIDO, M.ENTREGA, FP.CARTAO,
            [("Cenoura Orgânica da Terra", "2.000"), ("Batata-Doce Roxa", "2.000"), ("Cheiro-Verde Fresco (Coentro e Cebolinha)", 3)],
            dias_atras=2, entregador_uname="ent_thiago", taxa="8.00",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000007"] = _criar_pedido(
            "PED-RN000007", "lucas_bezerra", "prod_cearamirim", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Macaxeira Descascada a Vácuo", "2.000"), ("Couve-Folha Orgânica", 2), ("Alface Americana Orgânica", 2)],
            dias_atras=2, entregador_uname="ent_juliana", taxa="7.00",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )
        pedidos_map["PED-RN000008"] = _criar_pedido(
            "PED-RN000008", "fernanda_lima", "prod_serido", S.CONCLUIDO, M.RETIRADA, FP.DINHEIRO,
            [("Doce de Leite Artesanal (400 g)", 2), ("Nata Fresca do Seridó (300 g)", 2)],
            dias_atras=2, entregador_uname=None, taxa="0.00",
            previsao="Retirado no ponto de apoio",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.CONCLUIDO],
        )
        # Pedido CONCLUIDO de cliente_demo SEM avaliação (para demonstrar avaliação ao vivo + aviso no banner!)
        pedidos_map["PED-RN000009"] = _criar_pedido(
            "PED-RN000009", "cliente_demo", "prod_serido", S.CONCLUIDO, M.ENTREGA, FP.PIX,
            [("Queijo de Coalho Artesanal de Caicó", "0.800"), ("Ovos Caipiras (Dúzia)", 1)],
            dias_atras=1, entregador_uname="ent_thiago", taxa="7.50",
            observacao="Pedido entregue ontem — pronto para avaliar na demonstração.",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA, S.CONCLUIDO],
        )

        # ── 2 Pedidos PENDENTE para produtor_demo (aceitar/recusar ao vivo) ──
        pedidos_map["PED-RN000010"] = _criar_pedido(
            "PED-RN000010", "rafael_costa", "produtor_demo", S.PENDENTE, M.ENTREGA, FP.PIX,
            [("Alface Crespa Orgânica", 3), ("Tomate Cereja Agroecológico", "1.000"), ("Cenoura Orgânica da Terra", "1.500")],
            dias_atras=0, taxa="7.50",
            observacao="Entregar preferencialmente após as 16h.",
            historico_steps=[S.PENDENTE],
        )
        pedidos_map["PED-RN000011"] = _criar_pedido(
            "PED-RN000011", "fernanda_lima", "produtor_demo", S.PENDENTE, M.RETIRADA, FP.DINHEIRO,
            [("Batata-Doce Roxa", "3.000"), ("Cheiro-Verde Fresco (Coentro e Cebolinha)", 2)],
            dias_atras=0, taxa="0.00",
            observacao="Retiro na manhã de sábado.",
            historico_steps=[S.PENDENTE],
        )

        # ── 2 Pedidos em preparo / aceito (funil produtor + card ativo de cliente_demo) ──
        pedidos_map["PED-RN000012"] = _criar_pedido(
            "PED-RN000012", "lucas_bezerra", "produtor_demo", S.ACEITO, M.ENTREGA, FP.CARTAO,
            [("Mel de Abelha Jandaíra (300 ml)", 1), ("Alface Crespa Orgânica", 2)],
            dias_atras=0, taxa="7.50",
            previsao="Hoje entre 15h e 18h",
            historico_steps=[S.PENDENTE, S.ACEITO],
        )
        pedidos_map["PED-RN000013"] = _criar_pedido(
            "PED-RN000013", "cliente_demo", "produtor_demo", S.EM_PREPARO, M.ENTREGA, FP.PIX,
            [("Cenoura Orgânica da Terra", "1.500"), ("Cheiro-Verde Fresco (Coentro e Cebolinha)", 2), ("Tomate Cereja Agroecológico", "1.000")],
            dias_atras=0, taxa="7.00",
            previsao="Hoje entre 16h e 18h",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO],
        )

        # ── 3 Pedidos PRONTO disponíveis para entrega (entregador=None → aba Disponíveis) ──
        pedidos_map["PED-RN000014"] = _criar_pedido(
            "PED-RN000014", "ana_beatriz", "produtor_demo", S.PRONTO, M.ENTREGA, FP.PIX,
            [("Alface Crespa Orgânica", 2), ("Batata-Doce Roxa", "1.500")],
            dias_atras=0, entregador_uname=None, taxa="7.50",
            previsao="Pronto para retirada pelo entregador",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO],
        )
        pedidos_map["PED-RN000015"] = _criar_pedido(
            "PED-RN000015", "rafael_costa", "prod_serido", S.PRONTO, M.ENTREGA, FP.PIX,
            [("Queijo de Coalho Artesanal de Caicó", "1.000"), ("Manteiga da Terra (Garrafa 500 ml)", 1)],
            dias_atras=0, entregador_uname=None, taxa="9.00",
            previsao="Aguardando entregador",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO],
        )
        pedidos_map["PED-RN000016"] = _criar_pedido(
            "PED-RN000016", "fernanda_lima", "prod_valeverde", S.PRONTO, M.ENTREGA, FP.DINHEIRO,
            [("Caju Vermelho da Safra", "1.500"), ("Maracujá Azedo para Suco", "1.000"), ("Mamão Formosa", "1.500")],
            dias_atras=0, entregador_uname=None, taxa="8.00",
            previsao="Pronto no pomar",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO],
        )

        # ── 1 Pedido PRONTO já aceito por entregador_demo (pronto para "Saiu para entrega") ──
        pedidos_map["PED-RN000017"] = _criar_pedido(
            "PED-RN000017", "lucas_bezerra", "prod_cearamirim", S.PRONTO, M.ENTREGA, FP.PIX,
            [("Macaxeira Descascada a Vácuo", "2.000"), ("Pimentão Verde Agroecológico", "1.000")],
            dias_atras=0, entregador_uname="entregador_demo", taxa="7.50",
            previsao="Retirada agendada hoje",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO],
        )

        # ── 1 Pedido EM_ENTREGA com entregador_demo (pronto para "Confirmar entrega") ──
        pedidos_map["PED-RN000018"] = _criar_pedido(
            "PED-RN000018", "cliente_demo", "prod_mossoro", S.EM_ENTREGA, M.ENTREGA, FP.PIX,
            [("Melão Amarelo de Mossoró", "2.000"), ("Jerimum Caboclo (Fatia / Kg)", "1.500")],
            dias_atras=0, entregador_uname="entregador_demo", taxa="8.00",
            previsao="Em rota para Lagoa Nova",
            historico_steps=[S.PENDENTE, S.ACEITO, S.EM_PREPARO, S.PRONTO, S.EM_ENTREGA],
        )

        # ── 2 Pedidos de exceção (CANCELADO e RECUSADO — completam métricas dos dashboards) ──
        pedidos_map["PED-RN000019"] = _criar_pedido(
            "PED-RN000019", "rafael_costa", "sitio_esperanca", S.CANCELADO, M.ENTREGA, FP.PIX,
            [("Banana Prata Climatizada", "2.000")],
            dias_atras=3, taxa="7.00",
            motivo="Precisei viajar de última hora e não haveria quem recebesse em casa.",
            historico_steps=[S.PENDENTE, S.CANCELADO],
        )
        pedidos_map["PED-RN000020"] = _criar_pedido(
            "PED-RN000020", "lucas_bezerra", "produtor_demo", S.RECUSADO, M.ENTREGA, FP.DINHEIRO,
            [("Mel de Abelha Jandaíra (300 ml)", 3)],
            dias_atras=2, taxa="7.50",
            motivo="Lote de mel esgotado na feira presencial; nova remessa disponível na próxima semana.",
            historico_steps=[S.PENDENTE, S.RECUSADO],
        )
        self._ok(f"{len(pedidos_map)} pedidos realistas distribuídos em todos os status")

        # ── 8. Avaliações reais vinculadas a pedidos CONCLUIDO ──────────
        avaliacoes_prod_spec = [
            ("PED-RN000001", "cliente_demo", "produtor_demo", "Alface Crespa Orgânica", 5,
             "Alface muito fresca e crocante, chegou parecendo recém-colhida da horta!"),
            ("PED-RN000001", "cliente_demo", "produtor_demo", "Tomate Cereja Agroecológico", 5,
             "Tomate cereja super docinho e bem embalado."),
            ("PED-RN000001", "cliente_demo", "produtor_demo", "Mel de Abelha Jandaíra (300 ml)", 5,
             "Mel nativo autêntico, sabor delicado maravilhoso."),
            ("PED-RN000002", "ana_beatriz", "prod_serido", "Queijo de Coalho Artesanal de Caicó", 5,
             "Melhor queijo de coalho de Caicó! Não derrete na assadeira e tem sal na medida."),
            ("PED-RN000002", "ana_beatriz", "prod_serido", "Manteiga da Terra (Garrafa 500 ml)", 5,
             "Aroma incrível no cuscuz, manteiga puríssima."),
            ("PED-RN000002", "ana_beatriz", "prod_serido", "Ovos Caipiras (Dúzia)", 4,
             "Ovos excelentes e gema bem viva, entrega cuidadosa sem nenhum trincado."),
            ("PED-RN000003", "lucas_bezerra", "prod_valeverde", "Caju Vermelho da Safra", 5,
             "Cajus doces e suculentos direto de Nísia Floresta."),
            ("PED-RN000003", "lucas_bezerra", "prod_valeverde", "Manga Rosa Madura", 4,
             "Mangas muito saborosas e no ponto certo para consumo."),
            ("PED-RN000004", "fernanda_lima", "sitio_esperanca", "Alface Crespa Hidropônica", 5,
             "Folhas impecáveis e limpinhas, durou a semana inteira na geladeira."),
            ("PED-RN000004", "fernanda_lima", "sitio_esperanca", "Mel Puro de Abelha Tiúba", 5,
             "Qualidade excelente, recomendo demais."),
            ("PED-RN000005", "rafael_costa", "prod_mossoro", "Melão Amarelo de Mossoró", 5,
             "Melão extremamente doce, padrão de exportação!"),
            ("PED-RN000005", "rafael_costa", "prod_mossoro", "Feijão Verde Debulhado", 5,
             "Feijão verde fresquinho e já debulhado, facilitou muito o almoço de domingo."),
            ("PED-RN000006", "ana_beatriz", "produtor_demo", "Cenoura Orgânica da Terra", 5,
             "Cenouras firmes e doces, dá para sentir a diferença do cultivo orgânico."),
            ("PED-RN000007", "lucas_bezerra", "prod_cearamirim", "Macaxeira Descascada a Vácuo", 5,
             "Cozinhou em 15 minutos e ficou super macia, excelente!"),
        ]
        total_av = 0
        for num_ped, cli_u, prod_u, nome_prod, nota, coment in avaliacoes_prod_spec:
            _, _ = Avaliacao.objects.get_or_create(
                cliente=clientes[cli_u],
                produto=produtos_map[(prod_u, nome_prod)],
                pedido=pedidos_map[num_ped],
                defaults={"nota": nota, "comentario": coment},
            )
            total_av += 1

        avaliacoes_produtor_spec = [
            ("PED-RN000001", "cliente_demo", "produtor_demo", 5,
             "Atendimento atencioso do Sítio Serra Verde e produtos fresquíssimos."),
            ("PED-RN000006", "ana_beatriz", "produtor_demo", 5,
             "Pedido aceito rapidamente e tudo chegou muito bem acondicionado."),
            ("PED-RN000002", "ana_beatriz", "prod_serido", 5,
             "Produtos legítimos do Seridó, virei cliente fiel!"),
            ("PED-RN000003", "lucas_bezerra", "prod_valeverde", 5,
             "Frutas da estação de primeira qualidade."),
            ("PED-RN000004", "fernanda_lima", "sitio_esperanca", 5,
             "Pontualidade e capricho na seleção das hortaliças."),
            ("PED-RN000005", "rafael_costa", "prod_mossoro", 5,
             "Excelente comunicação e qualidade impecável dos produtos de Mossoró."),
            ("PED-RN000007", "lucas_bezerra", "prod_cearamirim", 4,
             "Verduras muito frescas, recomendo a Horta do Vale."),
        ]
        for num_ped, cli_u, prod_u, nota, coment in avaliacoes_produtor_spec:
            _, _ = Avaliacao.objects.get_or_create(
                cliente=clientes[cli_u],
                produtor=perfis_produtores[prod_u],
                pedido=pedidos_map[num_ped],
                defaults={"nota": nota, "comentario": coment},
            )
            total_av += 1

        avaliacoes_clientes_spec = [
            ("PED-RN000001", "produtor_demo", "cliente_demo", 5,
             "Cliente pontual, pagamento Pix confirmado rapidamente e ótima comunicação."),
            ("PED-RN000006", "produtor_demo", "ana_beatriz", 5,
             "Recebimento tranquilo e muito educada na entrega."),
            ("PED-RN000002", "prod_serido", "ana_beatriz", 5,
             "Excelente compradora, recomendadíssima."),
            ("PED-RN000004", "sitio_esperanca", "fernanda_lima", 5,
             "Endereço bem especificado e recebimento ágil na portaria."),
            ("PED-RN000005", "prod_mossoro", "rafael_costa", 5,
             "Compra tranquila, cliente muito cordial."),
        ]
        for num_ped, prod_u, cli_u, nota, coment in avaliacoes_clientes_spec:
            _, _ = AvaliacaoCliente.objects.get_or_create(
                pedido=pedidos_map[num_ped],
                defaults={
                    "produtor": perfis_produtores[prod_u],
                    "cliente": clientes[cli_u],
                    "nota": nota,
                    "comentario": coment,
                },
            )
            total_av += 1
        self._ok(f"{total_av} avaliações reais (produtos, produtores e recíprocas)")

        # ── 9. Reclamações (1 aberta na Fila Admin + 1 em análise + 1 resolvida) ──
        reclamacoes_spec = [
            (
                "PED-RN000009", "cliente_demo",
                "Atraso de 20 minutos na janela de entrega",
                "O produto chegou em ótimo estado, porém houve um pequeno atraso em relação ao horário combinado.",
                Reclamacao.Status.ABERTA, "",
            ),
            (
                "PED-RN000003", "lucas_bezerra",
                "Duas goiabas chegaram amassadas",
                "A maior parte das frutas estava ótima, mas duas unidades ficaram machucadas no transporte.",
                Reclamacao.Status.EM_ANALISE,
                "Estamos verificando com o produtor e o entregador para reforçar o acondicionamento.",
            ),
            (
                "PED-RN000002", "ana_beatriz",
                "Dúvida sobre comprovante Pix",
                "Solicitei a confirmação do recebimento do Pix e fui prontamente atendida.",
                Reclamacao.Status.RESOLVIDA,
                "Pagamento confirmado com o produtor e pedido concluído normalmente. Obrigado pelo retorno!",
            ),
        ]
        for num_ped, cli_u, assunto, desc, st, resp in reclamacoes_spec:
            Reclamacao.objects.get_or_create(
                cliente=clientes[cli_u],
                pedido=pedidos_map[num_ped],
                assunto=assunto,
                defaults={"descricao": desc, "status": st, "resposta_admin": resp},
            )
        self._ok(f"{len(reclamacoes_spec)} reclamações (aberta, em análise e resolvida)")

        # ── 10. Logs de Auditoria administrativos ───────────────────────
        auditorias_spec = [
            (LogAuditoria.Acao.APROVAR_PRODUTOR, "Produtor 'Sítio Serra Verde' (Macaíba/RN) aprovado para venda pública."),
            (LogAuditoria.Acao.APROVAR_PRODUTOR, "Produtor 'Fazenda Sabores do Seridó' (Caicó/RN) aprovado para venda pública."),
            (LogAuditoria.Acao.APROVAR_PRODUTOR, "Produtor 'Chácara Vale Verde' (Nísia Floresta/RN) aprovado para venda pública."),
            (LogAuditoria.Acao.APROVAR_PRODUTOR, "Produtor 'Horta Agroecológica do Vale' (Ceará-Mirim/RN) aprovado para venda pública."),
            (LogAuditoria.Acao.APROVAR_PRODUTOR, "Produtor 'Sítio Sol Nascente' (Mossoró/RN) aprovado para venda pública."),
            (LogAuditoria.Acao.MODERAR_RECLAMACAO, "Reclamação do pedido PED-RN000002 marcada como RESOLVIDA pela moderação."),
        ]
        for acao, desc in auditorias_spec:
            LogAuditoria.objects.get_or_create(
                usuario=admin,
                acao=acao,
                descricao=desc,
                defaults={"ip": "127.0.0.1"},
            )
        self._ok(f"{len(auditorias_spec)} registros em LogAuditoria")

        return {
            "produtores": len(perfis_produtores),
            "produtores_pendentes": sum(1 for p in perfis_produtores.values() if p.status == PerfilProdutor.Status.PENDENTE),
            "produtos": len(produtos_map),
            "clientes": len(clientes),
            "entregadores": len(entregadores),
            "pedidos": len(pedidos_map),
            "avaliacoes": total_av,
            "reclamacoes": len(reclamacoes_spec),
        }

    def _ok(self, msg):
        self.stdout.write(f"  ✓ {msg}")
