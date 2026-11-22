from decimal import Decimal

from django.test import override_settings
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Produto
from usuarios.models import Usuario

PW = "Senha-Forte-123"


class FluxoCompletoTest(APITestCase):
    def registrar(self, tipo, username, **extra):
        r = self.client.post(f"/api/auth/registro/{tipo}/", {
            "username": username, "email": f"{username}@ex.com", "password": PW,
            "first_name": username.title(), **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def login(self, username):
        r = self.client.post("/api/auth/login/", {"username": username, "password": PW}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r.data

    def setUp(self):
        Usuario.objects.create_superuser("admin", "admin@ex.com", PW)
        self.registrar("produtor", "maria", nome_propriedade="Sítio Esperança", chave_pix="maria@pix",
                       possui_maquininha=False)
        self.registrar("cliente", "joao")
        self.registrar("entregador", "zeca", veiculo="Moto")
        self.cat = Categoria.objects.create(nome="Hortaliças")

    def test_fluxo(self):
        # produtor cadastra produto (ainda pendente de aprovação → invisível no catálogo)
        self.login("maria")
        r = self.client.post("/api/produtor/produtos/", {
            "nome": "Alface", "preco": "3.50", "unidade_medida": "MACO", "estoque": "10",
            "tipo_producao": "AGROECOLOGICO", "categoria": self.cat.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        pid = r.data["id"]
        self.client.credentials()
        self.assertEqual(self.client.get("/api/produtos/").data["count"], 0)

        # admin aprova → aparece no catálogo, com busca e filtro
        self.login("admin")
        prod_id = self.client.get("/api/admin/produtores/").data["results"][0]["id"]
        self.assertEqual(self.client.post(f"/api/admin/produtores/{prod_id}/aprovar/").status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.get("/api/produtos/?search=alf").data["count"], 1)
        self.assertEqual(self.client.get("/api/produtos/?tipo_producao=CONVENCIONAL").data["count"], 0)

        # cliente: carrinho
        self.login("joao")
        r = self.client.post("/api/carrinho/itens/", {"produto": pid, "quantidade": "11"}, format="json")
        self.assertEqual(r.status_code, 400)  # acima do estoque
        r = self.client.post("/api/carrinho/itens/", {"produto": pid, "quantidade": "4"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        item = r.data["id"]
        self.client.patch(f"/api/carrinho/itens/{item}/", {"quantidade": "5"}, format="json")
        self.assertEqual(Decimal(self.client.get("/api/carrinho/").data["total"]), Decimal("17.50"))

        # checkout: sem endereço falha; cartão não aceito; pix ok
        base = {"modalidade": "ENTREGA", "forma_pagamento": "PIX"}
        self.assertEqual(self.client.post("/api/pedidos/", base, format="json").status_code, 400)
        end = self.client.post("/api/enderecos/", {"logradouro": "Rua A", "numero": "10", "bairro": "Centro",
                                                    "cidade": "Natal", "estado": "RN"}, format="json").data["id"]
        r = self.client.post("/api/pedidos/", {**base, "forma_pagamento": "CARTAO", "endereco_id": end}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/pedidos/", {**base, "endereco_id": end}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        pedido = r.data[0]["id"]
        self.assertEqual(self.client.post("/api/pedidos/", {**base, "endereco_id": end}, format="json").status_code, 400)  # carrinho vazio

        # não pode avaliar antes de comprar
        r = self.client.post("/api/avaliacoes/", {"produto": pid, "nota": 5}, format="json")
        self.assertEqual(r.status_code, 400)

        # produtor aceita → estoque baixa; outro produtor não poderia mexer
        self.login("maria")
        self.assertEqual(self.client.post(f"/api/produtor/pedidos/{pedido}/aceitar/").status_code, 200)
        self.assertEqual(Produto.objects.get(pk=pid).estoque, Decimal("5"))
        self.client.post(f"/api/produtor/pedidos/{pedido}/status/", {"status": "EM_PREPARO"}, format="json")
        r = self.client.post(f"/api/produtor/pedidos/{pedido}/status/", {"status": "PRONTO"}, format="json")
        self.assertEqual(r.data["status"], "PRONTO")
        # produtor não conclui pedido com entrega
        r = self.client.post(f"/api/produtor/pedidos/{pedido}/status/", {"status": "CONCLUIDO"}, format="json")
        self.assertEqual(r.status_code, 400)

        # entregador
        self.login("zeca")
        self.assertEqual(self.client.get("/api/entregas/").data["count"], 1)
        self.assertEqual(self.client.post(f"/api/entregas/{pedido}/aceitar/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/entregas/{pedido}/saiu-para-entrega/").data["status"], "EM_ENTREGA")
        self.assertEqual(self.client.post(f"/api/entregas/{pedido}/confirmar/").data["status"], "CONCLUIDO")

        # cliente avalia; não duplica
        self.login("joao")
        self.assertEqual(self.client.post("/api/avaliacoes/", {"produto": pid, "nota": 5, "comentario": "Fresquinha"},
                                          format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/avaliacoes/", {"produto": pid, "nota": 4}, format="json").status_code, 400)
        self.client.credentials()
        self.assertEqual(self.client.get("/api/produtos/").data["results"][0]["nota_media"], 5.0)

        # produtor vê vendas; admin vê indicadores
        self.login("maria")
        self.assertEqual(Decimal(str(self.client.get("/api/produtor/pedidos/vendas/").data["faturamento"])), Decimal("17.50"))
        self.login("admin")
        self.assertEqual(self.client.get("/api/admin/indicadores/").data["vendas_concluidas"], 1)

    def test_cancelamento_devolve_estoque_e_permissoes(self):
        Usuario.objects.get(username="maria").perfil_produtor.__class__.objects.update(status="APROVADO")
        perfil = Usuario.objects.get(username="maria").perfil_produtor
        p = Produto.objects.create(produtor=perfil, categoria=self.cat, nome="Mel", preco="20", estoque="3",
                                   unidade_medida="UNIDADE")
        self.login("joao")
        self.client.post("/api/carrinho/itens/", {"produto": p.id, "quantidade": "2"}, format="json")
        pedido = self.client.post("/api/pedidos/", {"modalidade": "RETIRADA", "forma_pagamento": "DINHEIRO"},
                                  format="json").data[0]["id"]
        self.login("maria")
        self.client.post(f"/api/produtor/pedidos/{pedido}/aceitar/")
        p.refresh_from_db(); self.assertEqual(p.estoque, Decimal("1"))
        self.login("joao")
        self.assertEqual(self.client.post(f"/api/pedidos/{pedido}/cancelar/").data["status"], "CANCELADO")
        p.refresh_from_db(); self.assertEqual(p.estoque, Decimal("3"))
        # cliente não acessa área do produtor/admin; produtor não cadastra categoria
        self.assertEqual(self.client.get("/api/produtor/pedidos/").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/usuarios/").status_code, 403)
        self.login("maria")
        self.assertEqual(self.client.post("/api/categorias/", {"nome": "X"}, format="json").status_code, 403)

    def test_logout_e_recuperacao_de_senha(self):
        tokens = self.login("joao")
        r = self.client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r.status_code, 204)
        r = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r.status_code, 401)
        from django.core import mail
        import re
        from urllib.parse import parse_qs
        self.client.credentials()
        self.client.post("/api/auth/recuperar-senha/", {"email": "joao@ex.com"}, format="json")
        corpo = mail.outbox[0].body
        match = re.search(r"#redefinir-senha\?([^\s]+)", corpo)
        self.assertIsNotNone(match, corpo)
        params = parse_qs(match.group(1))
        uid = params["uid"][0]
        token = params["token"][0]
        r = self.client.post("/api/auth/redefinir-senha/", {"uid": uid, "token": token, "nova_senha": "OutraSenha-987"},
                             format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_multiplos_produtores_geram_pedidos_separados(self):
        # Cria segundo produtor
        self.registrar("produtor", "pedro", nome_propriedade="Sítio do Pedro", chave_pix="pedro@pix")
        p2_user = Usuario.objects.get(username="pedro")
        p2_user.perfil_produtor.status = "APROVADO"
        p2_user.perfil_produtor.save()

        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()

        prod1 = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Batata",
                                       preco="4.00", estoque="10", unidade_medida="KG")
        prod2 = Produto.objects.create(produtor=p2_user.perfil_produtor, categoria=self.cat, nome="Abóbora",
                                       preco="6.00", estoque="10", unidade_medida="KG")

        self.login("joao")
        self.client.post("/api/carrinho/itens/", {"produto": prod1.id, "quantidade": "2"}, format="json")
        self.client.post("/api/carrinho/itens/", {"produto": prod2.id, "quantidade": "1"}, format="json")

        # Checkout deve gerar 2 pedidos distintos
        res = self.client.post("/api/pedidos/", {"modalidade": "RETIRADA", "forma_pagamento": "PIX"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data), 2)
        produtores_dos_pedidos = {p["produtor"] for p in res.data}
        self.assertEqual(len(produtores_dos_pedidos), 2)

    @override_settings(PIX_WEBHOOK_SECRET="segredo-pix-teste-seguro-2026")
    def test_pix_cobranca_e_webhook(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Morango",
                                      preco="12.00", estoque="10", unidade_medida="CAIXA")
        self.login("joao")
        self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "1"}, format="json")
        res = self.client.post("/api/pedidos/", {"modalidade": "RETIRADA", "forma_pagamento": "PIX"}, format="json")
        pedido_id = res.data[0]["id"]
        numero_publico = res.data[0]["numero_publico"]

        # Consulta dados Pix
        r_pix = self.client.get(f"/api/pedidos/{pedido_id}/pix/")
        self.assertEqual(r_pix.status_code, 200)
        self.assertIn("copia_e_cola", r_pix.data)
        self.assertTrue(r_pix.data.get("simulado"))
        self.assertNotIn("qr_code_url", r_pix.data)

        # Simula Webhook usando EXATAMENTE o txid retornado por gerar_cobranca()
        import hashlib
        import hmac
        import json
        txid = r_pix.data["txid"]
        payload = json.dumps({"txid": txid, "evento": "PAGAMENTO_CONFIRMADO"}).encode("utf-8")
        sig = hmac.new(b"segredo-pix-teste-seguro-2026", payload, hashlib.sha256).hexdigest()

        self.client.credentials()  # webhook é anônimo
        r_wh = self.client.post(
            "/api/pedidos/pix/webhook/",
            data=payload,
            content_type="application/json",
            HTTP_X_SIGNATURE=sig,
        )
        self.assertEqual(r_wh.status_code, 200)
        from .models import Pedido
        p_db = Pedido.objects.get(pk=pedido_id)
        self.assertEqual(p_db.status, Pedido.Status.ACEITO)

    @override_settings(DEBUG=False, PIX_WEBHOOK_SECRET="segredo-producao-forte")
    def test_webhook_pix_rejeita_segredo_antigo_e_default_em_producao(self):
        import hashlib
        import hmac
        import json
        from .pix import DEFAULT_DEV_SECRET

        payload = json.dumps({"txid": "ABC123", "evento": "PAGAMENTO_CONFIRMADO"}).encode("utf-8")
        sig_antiga = hmac.new(DEFAULT_DEV_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        self.client.credentials()
        r = self.client.post(
            "/api/pedidos/pix/webhook/",
            data=payload,
            content_type="application/json",
            HTTP_X_SIGNATURE=sig_antiga,
        )
        self.assertEqual(r.status_code, 401)

        with override_settings(DEBUG=False, PIX_WEBHOOK_SECRET=""):
            r_vazio = self.client.post(
                "/api/pedidos/pix/webhook/",
                data=payload,
                content_type="application/json",
                HTTP_X_SIGNATURE=sig_antiga,
            )
            self.assertEqual(r_vazio.status_code, 401)

        with override_settings(DEBUG=False, PIX_WEBHOOK_SECRET=DEFAULT_DEV_SECRET):
            r_default = self.client.post(
                "/api/pedidos/pix/webhook/",
                data=payload,
                content_type="application/json",
                HTTP_X_SIGNATURE=sig_antiga,
            )
            self.assertEqual(r_default.status_code, 401)

    @override_settings(TAXA_ENTREGA_PADRAO=Decimal("7.50"))
    def test_checkout_ignora_taxa_entrega_cliente_e_usa_servidor(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Tomate",
                                      preco="10.00", estoque="10", unidade_medida="KG")
        self.login("joao")
        end = self.client.post("/api/enderecos/", {"logradouro": "Rua B", "numero": "20", "bairro": "Centro",
                                                    "cidade": "Natal", "estado": "RN"}, format="json").data["id"]
        self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "2"}, format="json")
        res = self.client.post(
            "/api/pedidos/",
            {"modalidade": "ENTREGA", "forma_pagamento": "PIX", "endereco_id": end, "taxa_entrega": "-50.00"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data[0]["taxa_entrega"]), Decimal("7.50"))
        self.assertEqual(Decimal(res.data[0]["total_com_frete"]), Decimal("27.50"))

    def test_recusar_pedido_com_motivo(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Rúcula",
                                      preco="4.50", estoque="10", unidade_medida="MACO")
        self.login("joao")
        self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "1"}, format="json")
        res = self.client.post("/api/pedidos/", {"modalidade": "RETIRADA", "forma_pagamento": "DINHEIRO"}, format="json")
        pedido_id = res.data[0]["id"]

        self.login("maria")
        r_rec = self.client.post(
            f"/api/produtor/pedidos/{pedido_id}/recusar/",
            {"motivo": "Sem estoque fresco"},
            format="json",
        )
        self.assertEqual(r_rec.status_code, 200)
        self.assertEqual(r_rec.data["status"], "RECUSADO")
        self.assertEqual(r_rec.data["motivo_cancelamento"], "Sem estoque fresco")

    def test_patch_item_carrinho_nao_troca_produto_e_valida_unidade(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod_maco = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Coentro",
                                           preco="3.00", estoque="10", unidade_medida="MACO")
        prod_kg = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Batata Doce",
                                         preco="6.00", estoque="10", unidade_medida="KG")

        self.login("joao")
        # Unidade inteira rejeita decimal
        r_dec = self.client.post("/api/carrinho/itens/", {"produto": prod_maco.id, "quantidade": "1.5"}, format="json")
        self.assertEqual(r_dec.status_code, 400)

        # KG aceita decimal
        r_kg = self.client.post("/api/carrinho/itens/", {"produto": prod_kg.id, "quantidade": "1.500"}, format="json")
        self.assertEqual(r_kg.status_code, 201, r_kg.data)
        self.assertEqual(r_kg.data["produtor"], p1_user.perfil_produtor.id)
        self.assertEqual(r_kg.data["produtor_nome"], "Sítio Esperança")
        self.assertTrue(r_kg.data["aceita_pix"])

        # Adiciona segundo produto e tenta trocar produto via PATCH (não deve dar 500 nem trocar produto)
        r_maco = self.client.post("/api/carrinho/itens/", {"produto": prod_maco.id, "quantidade": "2"}, format="json")
        self.assertEqual(r_maco.status_code, 201)
        item_id = r_maco.data["id"]

        r_patch = self.client.patch(
            f"/api/carrinho/itens/{item_id}/",
            {"produto": prod_kg.id, "quantidade": "3"},
            format="json",
        )
        self.assertEqual(r_patch.status_code, 200, r_patch.data)
        self.assertEqual(r_patch.data["produto"], prod_maco.id)
        self.assertEqual(Decimal(r_patch.data["quantidade"]), Decimal("3"))

    def test_entregador_ve_endereco_resumido_antes_de_aceitar(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Laranja",
                                      preco="5.00", estoque="10", unidade_medida="KG")
        self.login("joao")
        end = self.client.post("/api/enderecos/", {
            "logradouro": "Rua das Flores", "numero": "42", "bairro": "Lagoa Nova",
            "cidade": "Natal", "estado": "RN", "cep": "59064-000"
        }, format="json").data["id"]
        self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "2"}, format="json")
        pedido_id = self.client.post("/api/pedidos/", {
            "modalidade": "ENTREGA", "forma_pagamento": "PIX", "endereco_id": end
        }, format="json").data[0]["id"]

        self.login("maria")
        self.client.post(f"/api/produtor/pedidos/{pedido_id}/aceitar/")

        self.login("zeca")
        r_disp = self.client.get("/api/entregas/?escopo=disponiveis")
        self.assertEqual(r_disp.status_code, 200)
        end_antes = r_disp.data["results"][0]["endereco_entrega"]
        self.assertNotIn("Rua das Flores", end_antes)
        self.assertIn("Lagoa Nova", end_antes)

        r_aceite = self.client.post(f"/api/entregas/{pedido_id}/aceitar/")
        self.assertEqual(r_aceite.status_code, 200)
        self.assertIn("Rua das Flores", r_aceite.data["endereco_entrega"])

    @override_settings(TAXA_ENTREGA_PADRAO=Decimal("8.50"))
    def test_entregador_resumo_historico_aceite_duplicado_e_isolamento(self):
        self.registrar("entregador", "zeca2", veiculo="Carro")
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.endereco_propriedade = "Estrada Rural km 5"
        p1_user.perfil_produtor.cidade = "Natal"
        p1_user.perfil_produtor.estado = "RN"
        p1_user.perfil_produtor.save()

        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Manga",
                                      preco="6.00", estoque="10", unidade_medida="KG")
        self.login("joao")
        end = self.client.post("/api/enderecos/", {
            "logradouro": "Av. Paulista", "numero": "100", "bairro": "Tirol",
            "cidade": "Natal", "estado": "RN", "cep": "59015-000"
        }, format="json").data["id"]
        self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "2"}, format="json")
        pedido_id = self.client.post("/api/pedidos/", {
            "modalidade": "ENTREGA", "forma_pagamento": "PIX", "endereco_id": end
        }, format="json").data[0]["id"]

        # Cliente e produtor não acessam endpoints de entregador
        self.assertEqual(self.client.get("/api/entregas/resumo/").status_code, 403)
        self.login("maria")
        self.assertEqual(self.client.get("/api/entregas/").status_code, 403)
        self.client.post(f"/api/produtor/pedidos/{pedido_id}/aceitar/")

        # Entregador 1 vê disponível com local de retirada e frete real
        self.login("zeca")
        r_res_antes = self.client.get("/api/entregas/resumo/")
        self.assertEqual(r_res_antes.status_code, 200)
        self.assertEqual(r_res_antes.data["disponiveis"], 1)
        r_disp = self.client.get("/api/entregas/?escopo=disponiveis")
        item = r_disp.data["results"][0]
        self.assertEqual(Decimal(item["taxa_entrega"]), Decimal("8.50"))
        self.assertIn("Estrada Rural km 5", item["local_retirada"])

        # Entregador 1 aceita -> Entregador 2 não vê mais nem pode aceitar
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/aceitar/").status_code, 200)
        self.login("zeca2")
        self.assertEqual(self.client.get("/api/entregas/?escopo=disponiveis").data["count"], 0)
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/aceitar/").status_code, 400)
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/saiu-para-entrega/").status_code, 404)

        # Entregador 1 não pode sair para entrega antes de o produtor marcar PRONTO
        self.login("zeca")
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/saiu-para-entrega/").status_code, 400)

        # Produtor prepara e marca pronto
        self.login("maria")
        self.client.post(f"/api/produtor/pedidos/{pedido_id}/status/", {"status": "EM_PREPARO"}, format="json")
        self.client.post(f"/api/produtor/pedidos/{pedido_id}/status/", {"status": "PRONTO"}, format="json")

        # Entregador 1 NÃO pode confirmar direto de PRONTO sem marcar saiu-para-entrega (BE-04)
        self.login("zeca")
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/confirmar/").status_code, 400)

        # Entregador 1 sai para entrega e conclui
        self.assertEqual(self.client.post(f"/api/entregas/{pedido_id}/saiu-para-entrega/").status_code, 200)
        r_conf = self.client.post(f"/api/entregas/{pedido_id}/confirmar/")
        self.assertEqual(r_conf.status_code, 200)
        self.assertIsNotNone(r_conf.data["concluido_em"])

        # Histórico e resumo com ganhos reais
        r_hist = self.client.get("/api/entregas/?escopo=historico")
        self.assertEqual(r_hist.data["count"], 1)
        r_res = self.client.get("/api/entregas/resumo/")
        self.assertEqual(r_res.data["concluidas"], 1)
        self.assertEqual(Decimal(str(r_res.data["ganhos_concluidos"])), Decimal("8.50"))

    def test_produtor_resumo_e_isolamento_propriedade(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "PENDENTE"
        p1_user.perfil_produtor.save()

        # Entregador não acessa painel do produtor
        self.login("zeca")
        self.assertEqual(self.client.get("/api/produtor/pedidos/resumo/").status_code, 403)
        self.assertEqual(self.client.patch("/api/perfil/produtor/", {"descricao": "Invasão"}, format="json").status_code, 403)

        # Produtor edita descrição da própria propriedade, mas não pode auto-aprovar status
        self.login("maria")
        r_patch = self.client.patch(
            "/api/perfil/produtor/",
            {"descricao": "Produção familiar certificada", "status": "APROVADO"},
            format="json",
        )
        self.assertEqual(r_patch.status_code, 200)
        self.assertEqual(r_patch.data["descricao"], "Produção familiar certificada")
        self.assertEqual(r_patch.data["status"], "PENDENTE")

        r_resumo = self.client.get("/api/produtor/pedidos/resumo/")
        self.assertEqual(r_resumo.status_code, 200)
        self.assertIsNone(r_resumo.data["media_avaliacoes_recebidas"])
        self.assertEqual(r_resumo.data["status_produtor"], "PENDENTE")

    def test_categoria_inativa_bloqueada_no_carrinho_e_checkout(self):
        p1_user = Usuario.objects.get(username="maria")
        p1_user.perfil_produtor.status = "APROVADO"
        p1_user.perfil_produtor.save()
        prod = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Cheiro Verde",
                                      preco="3.00", estoque="10", unidade_medida="MACO")
        self.login("joao")
        r_add = self.client.post("/api/carrinho/itens/", {"produto": prod.id, "quantidade": "1"}, format="json")
        self.assertEqual(r_add.status_code, 201)

        # Admin desativa a categoria após item já estar no carrinho -> checkout deve bloquear
        self.cat.ativa = False
        self.cat.save(update_fields=["ativa"])
        r_chk = self.client.post("/api/pedidos/", {"modalidade": "RETIRADA", "forma_pagamento": "PIX"}, format="json")
        self.assertEqual(r_chk.status_code, 400)

        # Novo item na categoria inativa também é bloqueado no carrinho
        prod2 = Produto.objects.create(produtor=p1_user.perfil_produtor, categoria=self.cat, nome="Salsa",
                                       preco="2.50", estoque="5", unidade_medida="MACO")
        r_add2 = self.client.post("/api/carrinho/itens/", {"produto": prod2.id, "quantidade": "1"}, format="json")
        self.assertEqual(r_add2.status_code, 400)
