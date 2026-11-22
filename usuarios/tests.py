from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from usuarios.models import Endereco, PerfilProdutor, Usuario

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

    def test_upload_foto_propriedade_produtor(self):
        buf = BytesIO()
        Image.new("RGB", (64, 64), color=(36, 111, 17)).save(buf, format="PNG")
        foto = SimpleUploadedFile("sitio.png", buf.getvalue(), content_type="image/png")

        dados = {
            "username": "sitio_com_foto",
            "email": "sitio_foto@exemplo.com",
            "password": PW,
            "nome_propriedade": "Sítio Recanto Verde",
            "descricao": "Agrofloresta familiar",
            "chave_pix": "recanto@pix",
            "foto_propriedade": foto,
        }
        res = self.client.post("/api/auth/registro/produtor/", dados, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = Usuario.objects.get(username="sitio_com_foto")
        self.assertTrue(bool(user.perfil_produtor.foto_propriedade))

        # Aprovar e verificar retorno no endpoint público /api/produtores/
        user.perfil_produtor.status = PerfilProdutor.Status.APROVADO
        user.perfil_produtor.save(update_fields=["status"])

        res_pub = self.client.get(f"/api/produtores/{user.perfil_produtor.id}/")
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res_pub.data["foto_propriedade"])

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

        # Excluir / Anonimizar sem senha ou com senha incorreta deve falhar
        res_del_no_pw = self.client.delete("/api/perfil/excluir-conta/", {}, format="json")
        self.assertEqual(res_del_no_pw.status_code, status.HTTP_400_BAD_REQUEST)
        res_del_bad_pw = self.client.delete("/api/perfil/excluir-conta/", {"password": "Errada-123!"}, format="json")
        self.assertEqual(res_del_bad_pw.status_code, status.HTTP_400_BAD_REQUEST)

        # Excluir / Anonimizar com senha correta
        res_del = self.client.delete("/api/perfil/excluir-conta/", {"password": PW}, format="json")
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_active)
        self.assertIsNotNone(self.cliente.excluido_em)
        self.assertIn("anonimo_", self.cliente.email)
        self.assertTrue(
            LogAuditoria.objects.filter(
                usuario=self.cliente,
                acao=LogAuditoria.Acao.EXCLUIR_CONTA_LGPD,
            ).exists()
        )

    def test_lgpd_excluir_conta_produtor_suspende_perfil_e_produtos(self):
        from catalogo.models import Categoria, Produto
        from decimal import Decimal

        perfil = PerfilProdutor.objects.create(
            usuario=self.produtor,
            nome_propriedade="Sítio LGPD",
            status=PerfilProdutor.Status.APROVADO,
            chave_pix="lgpd@pix",
        )
        cat = Categoria.objects.create(nome="LGPD Cat", ativa=True)
        prod = Produto.objects.create(
            produtor=perfil, categoria=cat, nome="Couve LGPD",
            preco=Decimal("4.00"), estoque=Decimal("10"), unidade_medida=Produto.Unidade.MACO, ativo=True,
        )
        tokens = self.login("produtor_teste")
        res = self.client.delete("/api/perfil/excluir-conta/", {"password": PW}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        perfil.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(perfil.status, PerfilProdutor.Status.SUSPENSO)
        self.assertIsNotNone(perfil.excluido_em)
        self.assertEqual(perfil.chave_pix, "")
        self.assertFalse(prod.ativo)
        self.assertIsNotNone(prod.excluido_em)
        # Refresh token invalidado
        r_ref = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r_ref.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_impede_revogar_token_de_outro_usuario(self):
        tokens_cli = self.login("cliente_teste")
        self.login("produtor_teste")
        res = self.client.post("/api/auth/logout/", {"refresh": tokens_cli["refresh"]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_path_traversal_assets_bloqueado(self):
        res = self.client.get("/assets/../../manage.py")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        res2 = self.client.get("/assets/../index.html")
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

    def test_config_publica_e_link_recuperacao_senha(self):
        from django.core import mail
        from django.test import override_settings

        with override_settings(DEBUG=False, SHOW_DEMO_SHORTCUTS=False, TAXA_ENTREGA_PADRAO="4.50"):
            res = self.client.get("/api/config/")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            data = res.json()
            self.assertFalse(data["demo"])
            self.assertNotIn("demo_accounts", data)
            self.assertEqual(data["taxa_entrega_padrao"], "4.50")

        # DEBUG=True sozinho não expõe demo_accounts sem SHOW_DEMO_SHORTCUTS=True
        with override_settings(DEBUG=True, SHOW_DEMO_SHORTCUTS=False):
            res_dbg = self.client.get("/api/config/")
            self.assertFalse(res_dbg.json()["demo"])
            self.assertNotIn("demo_accounts", res_dbg.json())

        with override_settings(DEBUG=True, SHOW_DEMO_SHORTCUTS=True):
            res_dev = self.client.get("/api/config/")
            self.assertTrue(res_dev.json()["demo"])
            self.assertIn("demo_accounts", res_dev.json())

        res_rec = self.client.post("/api/auth/recuperar-senha/", {"email": "cliente@exemplo.com"}, format="json")
        self.assertEqual(res_rec.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("/#redefinir-senha?uid=", body)
        self.assertIn("&token=", body)
        self.assertNotIn("POST /api/auth/redefinir-senha/", body)
        self.assertNotIn("\nuid: ", body)
