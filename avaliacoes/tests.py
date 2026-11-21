from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase
from avaliacoes.models import Avaliacao, Reclamacao
from catalogo.models import Categoria, Produto
from pedidos.models import ItemPedido, Pedido
from usuarios.models import PerfilProdutor, Usuario

PW = "Senha-Forte-123!"


class AvaliacoesTests(APITestCase):
    def setUp(self):
        self.cliente = Usuario.objects.create_user("cliente_av", "cli_av@ex.com", PW, tipo=Usuario.Tipo.CLIENTE)
        self.outro_cliente = Usuario.objects.create_user("outro_cli", "outro@ex.com", PW, tipo=Usuario.Tipo.CLIENTE)
        self.produtor_user = Usuario.objects.create_user("prod_av", "prod_av@ex.com", PW, tipo=Usuario.Tipo.PRODUTOR)
        self.perfil = PerfilProdutor.objects.create(
            usuario=self.produtor_user,
            nome_propriedade="Horta Viva",
            status=PerfilProdutor.Status.APROVADO,
        )
        self.cat = Categoria.objects.create(nome="Legumes", ativa=True)
        self.produto = Produto.objects.create(
            produtor=self.perfil,
            categoria=self.cat,
            nome="Cenoura",
            preco=Decimal("4.00"),
            estoque=Decimal("50"),
            unidade_medida=Produto.Unidade.KG,
            ativo=True,
        )

    def login(self, username):
        r = self.client.post("/api/auth/login/", {"username": username, "password": PW}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_avaliacao_so_quem_comprou(self):
        self.login("cliente_av")
        # Sem ter comprado
        r_erro = self.client.post("/api/avaliacoes/", {"produto": self.produto.id, "nota": 5}, format="json")
        self.assertEqual(r_erro.status_code, status.HTTP_400_BAD_REQUEST)

        # Simula pedido concluído
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            produtor=self.perfil,
            modalidade=Pedido.Modalidade.RETIRADA,
            forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
            status=Pedido.Status.CONCLUIDO,
            total=Decimal("8.00"),
        )
        ItemPedido.objects.create(
            pedido=pedido,
            produto=self.produto,
            nome_produto=self.produto.nome,
            unidade_medida=self.produto.unidade_medida,
            preco_unitario=self.produto.preco,
            quantidade=Decimal("2"),
        )

        # Avaliação com sucesso
        r_ok = self.client.post(
            "/api/avaliacoes/",
            {"produto": self.produto.id, "nota": 5, "comentario": "Excelente qualidade!"},
            format="json",
        )
        self.assertEqual(r_ok.status_code, status.HTTP_201_CREATED)

        # Não permite segunda avaliação no mesmo produto
        r_dupl = self.client.post("/api/avaliacoes/", {"produto": self.produto.id, "nota": 4}, format="json")
        self.assertEqual(r_dupl.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reclamacao_cliente_e_outro_cliente(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            produtor=self.perfil,
            modalidade=Pedido.Modalidade.RETIRADA,
            forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
            status=Pedido.Status.CONCLUIDO,
            total=Decimal("8.00"),
        )

        # Outro cliente não pode abrir reclamação no pedido alheio
        self.login("outro_cli")
        r_invalido = self.client.post(
            "/api/reclamacoes/",
            {"pedido": pedido.id, "assunto": "Problema", "descricao": "Não recebi"},
            format="json",
        )
        self.assertEqual(r_invalido.status_code, status.HTTP_400_BAD_REQUEST)

        # Titular do pedido abre com sucesso
        self.login("cliente_av")
        r_valido = self.client.post(
            "/api/reclamacoes/",
            {"pedido": pedido.id, "assunto": "Atraso", "descricao": "Demorou para entregar"},
            format="json",
        )
        self.assertEqual(r_valido.status_code, status.HTTP_201_CREATED)

    def test_produtor_avalia_cliente_apos_pedido_concluido_e_bloqueios(self):
        outro_prod_user = Usuario.objects.create_user("prod_av2", "prod_av2@ex.com", PW, tipo=Usuario.Tipo.PRODUTOR)
        PerfilProdutor.objects.create(
            usuario=outro_prod_user,
            nome_propriedade="Sítio Outro",
            status=PerfilProdutor.Status.APROVADO,
        )
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            produtor=self.perfil,
            modalidade=Pedido.Modalidade.RETIRADA,
            forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
            status=Pedido.Status.EM_PREPARO,
            total=Decimal("12.00"),
        )

        # Cliente não pode acessar endpoint exclusivo de produtor
        self.login("cliente_av")
        r_forb = self.client.post("/api/produtor/avaliacoes-clientes/", {"pedido": pedido.id, "nota": 5}, format="json")
        self.assertEqual(r_forb.status_code, status.HTTP_403_FORBIDDEN)

        # Produtor não pode avaliar antes da conclusão do pedido
        self.login("prod_av")
        r_antes = self.client.post("/api/produtor/avaliacoes-clientes/", {"pedido": pedido.id, "nota": 5}, format="json")
        self.assertEqual(r_antes.status_code, status.HTTP_400_BAD_REQUEST)

        # Conclui o pedido
        pedido.status = Pedido.Status.CONCLUIDO
        pedido.save(update_fields=["status"])

        # Outro produtor não pode avaliar cliente de pedido alheio
        self.login("prod_av2")
        r_alheio = self.client.post("/api/produtor/avaliacoes-clientes/", {"pedido": pedido.id, "nota": 4}, format="json")
        self.assertEqual(r_alheio.status_code, status.HTTP_400_BAD_REQUEST)

        # Produtor titular avalia com sucesso
        self.login("prod_av")
        r_ok = self.client.post(
            "/api/produtor/avaliacoes-clientes/",
            {"pedido": pedido.id, "nota": 5, "comentario": "Cliente pontual e educado."},
            format="json",
        )
        self.assertEqual(r_ok.status_code, status.HTTP_201_CREATED, r_ok.data)
        self.assertEqual(r_ok.data["cliente"], self.cliente.id)
        av_id = r_ok.data["id"]

        # Impede duplicidade para o mesmo pedido
        r_dup = self.client.post(
            "/api/produtor/avaliacoes-clientes/",
            {"pedido": pedido.id, "nota": 3},
            format="json",
        )
        self.assertEqual(r_dup.status_code, status.HTTP_400_BAD_REQUEST)

        # Impede edição ou exclusão (imutabilidade das avaliações)
        self.assertIn(
            self.client.patch(f"/api/produtor/avaliacoes-clientes/{av_id}/", {"nota": 1}, format="json").status_code,
            (status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED),
        )
        self.assertIn(
            self.client.delete(f"/api/produtor/avaliacoes-clientes/{av_id}/").status_code,
            (status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED),
        )

        # Consulta lista de avaliações feitas pelo produtor
        r_list = self.client.get("/api/produtor/avaliacoes-clientes/")
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertEqual(r_list.data["count"], 1)
        self.assertEqual(r_list.data["results"][0]["comentario"], "Cliente pontual e educado.")
