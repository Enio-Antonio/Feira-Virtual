from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase
from catalogo.models import Categoria, Produto
from painel.models import LogAuditoria
from usuarios.models import PerfilProdutor, Usuario

PW = "Senha-Forte-123!"


class PainelAdminTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser("admin_pnl", "admin_pnl@ex.com", PW)
        self.cliente = Usuario.objects.create_user("cliente_pnl", "cli_pnl@ex.com", PW, tipo=Usuario.Tipo.CLIENTE)
        self.produtor_user = Usuario.objects.create_user("prod_pnl", "prod_pnl@ex.com", PW, tipo=Usuario.Tipo.PRODUTOR)
        self.perfil = PerfilProdutor.objects.create(
            usuario=self.produtor_user,
            nome_propriedade="Chácara Sol",
            status=PerfilProdutor.Status.PENDENTE,
        )
        self.cat = Categoria.objects.create(nome="Frutas Pnl", ativa=True)
        self.produto = Produto.objects.create(
            produtor=self.perfil,
            categoria=self.cat,
            nome="Maçã",
            preco=Decimal("5.00"),
            estoque=Decimal("10"),
            unidade_medida=Produto.Unidade.KG,
            ativo=True,
        )

    def login(self, username):
        r = self.client.post("/api/auth/login/", {"username": username, "password": PW}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_permissoes_admin(self):
        # Cliente toma 403
        self.login("cliente_pnl")
        r = self.client.get("/api/admin/indicadores/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        # Produtor toma 403
        self.login("prod_pnl")
        r_prod = self.client.get("/api/admin/usuarios/")
        self.assertEqual(r_prod.status_code, status.HTTP_403_FORBIDDEN)

        # Admin tem acesso
        self.login("admin_pnl")
        r_admin = self.client.get("/api/admin/indicadores/")
        self.assertEqual(r_admin.status_code, status.HTTP_200_OK)

    def test_bloquear_e_reativar_usuario_com_auditoria(self):
        self.login("admin_pnl")
        # Bloquear cliente
        r_block = self.client.post(f"/api/admin/usuarios/{self.cliente.id}/bloquear/")
        self.assertEqual(r_block.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_active)

        # Checa registro de auditoria
        self.assertTrue(LogAuditoria.objects.filter(acao=LogAuditoria.Acao.BLOQUEAR_USUARIO).exists())

        # Reativar
        r_reat = self.client.post(f"/api/admin/usuarios/{self.cliente.id}/reativar/")
        self.assertEqual(r_reat.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)

    def test_aprovar_e_suspender_produtor(self):
        self.login("admin_pnl")
        # Aprovar
        r_aprov = self.client.post(f"/api/admin/produtores/{self.perfil.id}/aprovar/")
        self.assertEqual(r_aprov.status_code, status.HTTP_200_OK)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.status, PerfilProdutor.Status.APROVADO)

        # Suspender
        r_susp = self.client.post(f"/api/admin/produtores/{self.perfil.id}/suspender/")
        self.assertEqual(r_susp.status_code, status.HTTP_200_OK)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.status, PerfilProdutor.Status.SUSPENSO)

    def test_ocultar_e_reexibir_produto(self):
        self.login("admin_pnl")
        # Ocultar
        r_ocult = self.client.post(f"/api/admin/produtos/{self.produto.id}/ocultar/")
        self.assertEqual(r_ocult.status_code, status.HTTP_200_OK)
        self.produto.refresh_from_db()
        self.assertFalse(self.produto.ativo)

        # Reexibir
        r_reex = self.client.post(f"/api/admin/produtos/{self.produto.id}/reexibir/")
        self.assertEqual(r_reex.status_code, status.HTTP_200_OK)
        self.produto.refresh_from_db()
        self.assertTrue(self.produto.ativo)
