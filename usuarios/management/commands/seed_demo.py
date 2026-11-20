"""
Comando de demonstração: popula o banco com dados de teste.
Só pode rodar com DEBUG=True (nunca em produção).

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # apaga e recria tudo
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Cria dados de demonstração (só com DEBUG=1)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove dados existentes antes de criar novos",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo só pode rodar com DEBUG=1. "
                "Nunca execute em produção."
            )

        self.stdout.write(self.style.WARNING("⚠  Rodando seed_demo em modo DEBUG …"))

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            self._seed()

        self.stdout.write(self.style.SUCCESS("✅  Seed concluído com sucesso!"))
        self.stdout.write("")
        self.stdout.write("Contas criadas:")
        self.stdout.write("  Admin   → admin / admin-demo-2024")
        self.stdout.write("  Cliente → cliente@demo.com / cliente-demo-2024")
        self.stdout.write("  Produtor→ produtor@demo.com / produtor-demo-2024")
        self.stdout.write("  Entregad→ entregador@demo.com / entregador-demo-2024")

    # ------------------------------------------------------------------ #

    def _reset(self):
        """Remove dados de demonstração anteriores."""
        from catalogo.models import Categoria, Produto
        from usuarios.models import PerfilProdutor, Usuario

        self.stdout.write("  Removendo dados anteriores …")
        emails = [
            "admin@demo.com",
            "cliente@demo.com",
            "produtor@demo.com",
            "entregador@demo.com",
        ]
        Usuario.objects.filter(email__in=emails).delete()
        Categoria.objects.filter(nome__startswith="[DEMO]").delete()

    def _seed(self):
        from catalogo.models import Categoria, Produto
        from usuarios.models import PerfilEntregador, PerfilProdutor, Usuario

        # ── Superusuário admin ──────────────────────────────────────────
        admin, created = Usuario.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@demo.com",
                "first_name": "Admin",
                "last_name": "Demo",
                "tipo": Usuario.Tipo.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created or not admin.has_usable_password():
            admin.set_password("admin-demo-2024")
            admin.save()
        self._ok("Superusuário admin")

        # ── Cliente de teste ────────────────────────────────────────────
        cliente, created = Usuario.objects.get_or_create(
            email="cliente@demo.com",
            defaults={
                "username": "cliente_demo",
                "first_name": "Maria",
                "last_name": "Cliente",
                "tipo": Usuario.Tipo.CLIENTE,
            },
        )
        if created or not cliente.has_usable_password():
            cliente.set_password("cliente-demo-2024")
            cliente.save()
        self._ok("Cliente de teste (cliente@demo.com)")

        # ── Produtor aprovado ───────────────────────────────────────────
        produtor_user, created = Usuario.objects.get_or_create(
            email="produtor@demo.com",
            defaults={
                "username": "produtor_demo",
                "first_name": "João",
                "last_name": "Produtor",
                "tipo": Usuario.Tipo.PRODUTOR,
            },
        )
        if created or not produtor_user.has_usable_password():
            produtor_user.set_password("produtor-demo-2024")
            produtor_user.save()

        perfil_prod, _ = PerfilProdutor.objects.get_or_create(
            usuario=produtor_user,
            defaults={
                "nome_propriedade": "Sítio Esperança (Demo)",
                "descricao": "Produção orgânica familiar desde 1998.",
                "cidade": "Campinas",
                "estado": "SP",
                "status": PerfilProdutor.Status.APROVADO,
                "chave_pix": "produtor@demo.com",
            },
        )
        self._ok("Produtor aprovado (produtor@demo.com)")

        # ── Entregador ──────────────────────────────────────────────────
        entregador_user, created = Usuario.objects.get_or_create(
            email="entregador@demo.com",
            defaults={
                "username": "entregador_demo",
                "first_name": "Carlos",
                "last_name": "Entregador",
                "tipo": Usuario.Tipo.ENTREGADOR,
            },
        )
        if created or not entregador_user.has_usable_password():
            entregador_user.set_password("entregador-demo-2024")
            entregador_user.save()

        PerfilEntregador.objects.get_or_create(
            usuario=entregador_user,
            defaults={
                "veiculo": "Moto Honda 160",
                "placa": "ABC1D23",
                "area_atuacao": "Campinas e Região",
            },
        )
        self._ok("Entregador (entregador@demo.com)")

        # ── Categorias ──────────────────────────────────────────────────
        categorias_data = [
            ("Verduras e Legumes", "🥦"),
            ("Frutas", "🍎"),
            ("Ovos e Laticínios", "🥚"),
            ("Grãos e Cereais", "🌾"),
        ]
        cats = {}
        for nome, icone in categorias_data:
            cat, _ = Categoria.objects.get_or_create(
                nome=f"[DEMO] {nome}",
                defaults={"descricao": f"Categoria de {nome.lower()}", "ativa": True},
            )
            cats[nome] = cat
        self._ok(f"{len(cats)} categorias criadas")

        # ── Produtos ────────────────────────────────────────────────────
        produtos_data = [
            ("Alface Crespa Orgânica", "Verduras e Legumes", "2.50", 100, Produto.Unidade.MACO, Produto.TipoProducao.ORGANICO_CERTIFICADO),
            ("Tomate Cereja", "Verduras e Legumes", "8.90", 50, Produto.Unidade.KG, Produto.TipoProducao.ORGANICO_CERTIFICADO),
            ("Banana Prata (cacho)", "Frutas", "6.00", 80, Produto.Unidade.KG, Produto.TipoProducao.AGROECOLOGICO),
            ("Ovos Caipiras (dúzia)", "Ovos e Laticínios", "12.00", 200, Produto.Unidade.UNIDADE, Produto.TipoProducao.AGROECOLOGICO),
            ("Feijão Carioca (1kg)", "Grãos e Cereais", "9.50", 60, Produto.Unidade.KG, Produto.TipoProducao.CONVENCIONAL),
            ("Cenoura (1kg)", "Verduras e Legumes", "4.00", 90, Produto.Unidade.KG, Produto.TipoProducao.ORGANICO_CERTIFICADO),
        ]
        criados = 0
        for nome, cat_nome, preco, estoque, un, tipo_prod in produtos_data:
            _, created = Produto.objects.get_or_create(
                nome=nome,
                produtor=perfil_prod,
                defaults={
                    "descricao": f"{nome} fresquinho direto do sítio.",
                    "categoria": cats[cat_nome],
                    "preco": preco,
                    "estoque": estoque,
                    "unidade_medida": un,
                    "ativo": True,
                    "tipo_producao": tipo_prod,
                },
            )
            if created:
                criados += 1
        self._ok(f"{criados} produtos criados")

    def _ok(self, msg):
        self.stdout.write(f"  ✓ {msg}")
