from rest_framework import status
from rest_framework.test import APITestCase
from usuarios.models import Endereco, Usuario

PW = "Senha-Forte-123!"


class UsuariosTests(APITestCase):
    def setUp(self):
        self.cliente = Usuario.objects.create_user(
            username="cliente_teste",
            email="cliente@exemplo.com",
            password=PW,
            first_name="Cliente",
            tipo=Usuario.Tipo.CLIENTE,
        )
        self.produtor = Usuario.objects.create_user(
            username="produtor_teste",
            email="produtor@exemplo.com",
            password=PW,
            tipo=Usuario.Tipo.PRODUTOR,
        )

    def login(self, username):
        r = self.client.post("/api/auth/login/", {"username": username, "password": PW}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        token = r.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return r.data

    def test_registro_cliente_sucesso(self):
        dados = {
            "username": "novo_cliente",
            "email": "novo@exemplo.com",
            "password": PW,
            "first_name": "Novo",
            "last_name": "Cliente",
            "telefone": "11999998888",
        }
        res = self.client.post("/api/auth/registro/cliente/", dados, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Usuario.objects.filter(username="novo_cliente").exists())

    def test_registro_produtor_cria_perfil_pendente(self):
        dados = {
            "username": "sitio_novo",
            "email": "sitio@exemplo.com",
            "password": PW,
            "nome_propriedade": "Sítio Novo",
            "descricao": "Orgânicos e frutas",
            "chave_pix": "sitio@pix",
        }
        res = self.client.post("/api/auth/registro/produtor/", dados, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = Usuario.objects.get(username="sitio_novo")
        self.assertEqual(user.perfil_produtor.status, "PENDENTE")

    def test_meu_perfil_e_atualizacao(self):
        self.login("cliente_teste")
        res = self.client.get("/api/perfil/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "cliente_teste")

        # Atualizar telefone
        res_patch = self.client.patch("/api/perfil/", {"telefone": "19988776655"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.data["telefone"], "19988776655")

    def test_endereco_crud(self):
        self.login("cliente_teste")
        # Criar
        payload = {
            "rotulo": "Casa",
            "cep": "13010-000",
            "logradouro": "Av. Brasil",
            "numero": "500",
            "bairro": "Guanabara",
            "cidade": "Campinas",
            "estado": "SP",
        }
        res = self.client.post("/api/enderecos/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        end_id = res.data["id"]

        # Listar
        res_list = self.client.get("/api/enderecos/")
        self.assertEqual(len(res_list.data), 1)

        # Deletar
        res_del = self.client.delete(f"/api/enderecos/{end_id}/")
        self.assertEqual(res_del.status_code, status.HTTP_204_NO_CONTENT)

    def test_lgpd_exportar_e_excluir_conta(self):
        from painel.models import LogAuditoria

        self.login("cliente_teste")
        # Exportar
        res_exp = self.client.get("/api/perfil/exportar-dados/")
        self.assertEqual(res_exp.status_code, status.HTTP_200_OK)
        self.assertIn("titular", res_exp.data)
        self.assertEqual(res_exp.data["titular"]["email"], "cliente@exemplo.com")
        self.assertTrue(
            LogAuditoria.objects.filter(
                usuario=self.cliente,
                acao=LogAuditoria.Acao.EXPORTAR_DADOS_LGPD,
            ).exists()
        )

        # Excluir / Anonimizar
        res_del = self.client.delete("/api/perfil/excluir-conta/")
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_active)
        self.assertIn("anonimo_", self.cliente.email)
        self.assertTrue(
            LogAuditoria.objects.filter(
                usuario=self.cliente,
                acao=LogAuditoria.Acao.EXCLUIR_CONTA_LGPD,
            ).exists()
        )
