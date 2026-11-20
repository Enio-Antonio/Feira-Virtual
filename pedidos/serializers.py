from decimal import Decimal
import re

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalogo.models import Produto
from usuarios.models import Endereco

from .models import Carrinho, HistoricoStatus, ItemCarrinho, ItemPedido, Pedido

UNIDADES_INTEIRAS = {
    Produto.Unidade.UNIDADE,
    Produto.Unidade.CAIXA,
    Produto.Unidade.SACO,
    Produto.Unidade.MACO,
}


def _resumir_endereco_entregador(endereco_completo: str) -> str:
    if not endereco_completo:
        return ""
    if " - " in endereco_completo:
        parte = endereco_completo.split(" - ", 1)[1].strip()
        # Remove CEP no final (ex: "13010-000" ou "13010000")
        parte = re.sub(r"\s+\d{5}-?\d{3}$", "", parte).strip()
        return parte
    return "Endereço disponível após aceitar a entrega"


class ItemCarrinhoSerializer(serializers.ModelSerializer):
    produto_nome = serializers.CharField(source="produto.nome", read_only=True)
    preco_unitario = serializers.DecimalField(source="produto.preco", max_digits=10, decimal_places=2, read_only=True)
    unidade_medida = serializers.CharField(source="produto.unidade_medida", read_only=True)
    estoque = serializers.DecimalField(source="produto.estoque", max_digits=10, decimal_places=3, read_only=True)
    produtor = serializers.IntegerField(source="produto.produtor_id", read_only=True)
    produtor_nome = serializers.CharField(source="produto.produtor.nome_propriedade", read_only=True)
    aceita_pix = serializers.SerializerMethodField()
    possui_maquininha = serializers.BooleanField(source="produto.produtor.possui_maquininha", read_only=True)
    aceita_dinheiro = serializers.BooleanField(source="produto.produtor.aceita_dinheiro", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemCarrinho
        fields = [
            "id", "produto", "produto_nome", "preco_unitario", "unidade_medida", "estoque",
            "produtor", "produtor_nome", "aceita_pix", "possui_maquininha", "aceita_dinheiro",
            "quantidade", "subtotal",
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_aceita_pix(self, obj) -> bool:
        return bool((obj.produto.produtor.chave_pix or "").strip())

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["produto"].read_only = True
        return fields

    def validate(self, attrs):
        produto = attrs.get("produto") or self.instance.produto
        qtd = attrs.get("quantidade", getattr(self.instance, "quantidade", Decimal("0")))
        if not produto.ativo or produto.produtor.status != "APROVADO":
            raise serializers.ValidationError("Produto indisponível.")
        if qtd is None or qtd <= 0:
            raise serializers.ValidationError({"quantidade": "A quantidade deve ser maior que zero."})
        if produto.unidade_medida in UNIDADES_INTEIRAS and qtd != int(qtd):
            raise serializers.ValidationError(
                {"quantidade": f"Para a unidade '{produto.get_unidade_medida_display()}', informe uma quantidade inteira."}
            )
        if self.instance is None:  # soma com o que já está no carrinho
            existente = ItemCarrinho.objects.filter(
                carrinho=self.context["carrinho"], produto=produto).first()
            if existente:
                qtd = qtd + existente.quantidade
        if qtd > produto.estoque:
            raise serializers.ValidationError(f"Quantidade acima do estoque disponível ({produto.estoque}).")
        return attrs


class CarrinhoSerializer(serializers.ModelSerializer):
    itens = ItemCarrinhoSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Carrinho
        fields = ["id", "itens", "total"]


class ItemPedidoSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemPedido
        fields = ["id", "produto", "nome_produto", "unidade_medida", "preco_unitario", "quantidade", "subtotal"]


class HistoricoSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricoStatus
        fields = ["status", "criado_em"]


class PedidoSerializer(serializers.ModelSerializer):
    itens = ItemPedidoSerializer(many=True, read_only=True)
    historico = HistoricoSerializer(many=True, read_only=True)
    produtor_nome = serializers.CharField(source="produtor.nome_propriedade", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.get_full_name", read_only=True)
    total_com_frete = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    chave_pix = serializers.SerializerMethodField()
    endereco_entrega = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id", "numero_publico", "status", "modalidade", "forma_pagamento",
            "endereco_entrega", "observacao", "total", "taxa_entrega", "total_com_frete",
            "previsao_entrega", "motivo_cancelamento", "produtor", "produtor_nome",
            "cliente", "cliente_nome", "entregador", "chave_pix",
            "itens", "historico", "criado_em", "atualizado_em"
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_endereco_entrega(self, obj) -> str:
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False):
            u = request.user
            if getattr(u, "tipo", None) == "ENTREGADOR" and obj.entregador_id != u.id:
                return _resumir_endereco_entregador(obj.endereco_entrega)
        return obj.endereco_entrega

    def get_chave_pix(self, obj) -> str | None:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        # Proteção LGPD: Chave Pix só é visível ao cliente com pedido ativo ou ao produtor/admin
        u = request.user
        if u.id == obj.cliente_id or u.tipo in ("ADMIN", "PRODUTOR"):
            if obj.status not in (Pedido.Status.CANCELADO, Pedido.Status.RECUSADO):
                return obj.produtor.chave_pix
        return None


class CheckoutSerializer(serializers.Serializer):
    modalidade = serializers.ChoiceField(choices=Pedido.Modalidade.choices)
    forma_pagamento = serializers.ChoiceField(choices=Pedido.FormaPagamento.choices)
    endereco_id = serializers.IntegerField(required=False)
    observacao = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        endereco = None
        if attrs["modalidade"] == Pedido.Modalidade.ENTREGA:
            if "endereco_id" not in attrs:
                raise serializers.ValidationError({"endereco_id": "Informe o endereço de entrega."})
            try:
                endereco = Endereco.objects.get(pk=attrs["endereco_id"], usuario=self.context["request"].user)
            except Endereco.DoesNotExist:
                raise serializers.ValidationError({"endereco_id": "Endereço não encontrado."})
        attrs["endereco"] = endereco
        return attrs


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Pedido.Status.choices)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=500)
    previsao_entrega = serializers.CharField(required=False, allow_blank=True, max_length=120)
