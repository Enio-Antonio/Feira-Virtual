from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from pedidos.models import ItemPedido, Pedido

from .models import Avaliacao, AvaliacaoCliente, Reclamacao


class AvaliacaoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.SerializerMethodField()
    produto_nome = serializers.CharField(source="produto.nome", read_only=True, default=None)
    tipo_avaliacao = serializers.SerializerMethodField()

    class Meta:
        model = Avaliacao
        fields = [
            "id", "produto", "produto_nome", "produtor", "tipo_avaliacao",
            "nota", "comentario", "cliente_nome", "criado_em",
        ]
        read_only_fields = ["criado_em"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_cliente_nome(self, obj) -> str:
        nome = obj.cliente.get_full_name().strip()
        return nome or obj.cliente.first_name or obj.cliente.username

    @extend_schema_field(OpenApiTypes.STR)
    def get_tipo_avaliacao(self, obj) -> str:
        return "PRODUTO" if obj.produto_id else "PRODUTOR"

    def validate(self, attrs):
        produto, produtor = attrs.get("produto"), attrs.get("produtor")
        if bool(produto) == bool(produtor):
            raise serializers.ValidationError("Informe 'produto' OU 'produtor' (apenas um).")
        user = self.context["request"].user
        if produto:
            comprou = ItemPedido.objects.filter(produto=produto, pedido__cliente=user,
                                                pedido__status=Pedido.Status.CONCLUIDO).exists()
            ja = Avaliacao.objects.filter(cliente=user, produto=produto).exists()
        else:
            comprou = Pedido.objects.filter(produtor=produtor, cliente=user,
                                            status=Pedido.Status.CONCLUIDO).exists()
            ja = Avaliacao.objects.filter(cliente=user, produtor=produtor).exists()
        if not comprou:
            raise serializers.ValidationError("Somente clientes que compraram (pedido concluído) podem avaliar.")
        if ja:
            raise serializers.ValidationError("Você já avaliou este item.")
        return attrs


class ReclamacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reclamacao
        fields = ["id", "pedido", "assunto", "descricao", "status", "resposta_admin", "criado_em"]
        read_only_fields = ["status", "resposta_admin", "criado_em"]

    def validate_pedido(self, pedido):
        if pedido.cliente_id != self.context["request"].user.id:
            raise serializers.ValidationError("Pedido não encontrado.")
        return pedido


class ReclamacaoAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reclamacao
        fields = ["id", "cliente", "pedido", "assunto", "descricao", "status", "resposta_admin", "criado_em"]
        read_only_fields = ["cliente", "pedido", "assunto", "descricao", "criado_em"]


class AvaliacaoClienteSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.SerializerMethodField()
    produtor_nome = serializers.CharField(source="produtor.nome_propriedade", read_only=True)
    pedido_numero = serializers.CharField(source="pedido.numero_publico", read_only=True)

    class Meta:
        model = AvaliacaoCliente
        fields = [
            "id", "pedido", "pedido_numero", "cliente", "cliente_nome",
            "produtor", "produtor_nome", "nota", "comentario", "criado_em",
        ]
        read_only_fields = ["cliente", "produtor", "criado_em"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_cliente_nome(self, obj) -> str:
        nome = obj.cliente.get_full_name().strip()
        return nome or obj.cliente.first_name or obj.cliente.username

    def validate_pedido(self, pedido):
        user = self.context["request"].user
        perfil = getattr(user, "perfil_produtor", None)
        if not perfil or pedido.produtor_id != perfil.id:
            raise serializers.ValidationError("Você só pode avaliar clientes de pedidos da sua propriedade.")
        if pedido.status != Pedido.Status.CONCLUIDO:
            raise serializers.ValidationError("A avaliação do cliente só é permitida após a conclusão do pedido.")
        if AvaliacaoCliente.objects.filter(pedido=pedido).exists():
            raise serializers.ValidationError("Você já avaliou o cliente para este pedido.")
        return pedido
