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
