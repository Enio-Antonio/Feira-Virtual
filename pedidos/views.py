from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EhCliente, EhEntregador, EhProdutor

from . import services
from .models import Carrinho, ItemCarrinho, Pedido
from .serializers import (CarrinhoSerializer, CheckoutSerializer, ItemCarrinhoSerializer,
                          PedidoSerializer, StatusSerializer)

S = Pedido.Status
_pedidos_qs = Pedido.objects.select_related("produtor", "cliente").prefetch_related("itens", "historico")


def _carrinho(user):
    return Carrinho.objects.get_or_create(cliente=user)[0]


class CarrinhoView(APIView):
    permission_classes = [EhCliente]
    serializer_class = CarrinhoSerializer

    def get(self, request):
        return Response(CarrinhoSerializer(_carrinho(request.user)).data)

    def delete(self, request):
        _carrinho(request.user).itens.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemCarrinhoViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    """Adicionar, alterar quantidade e remover itens do carrinho."""
    serializer_class = ItemCarrinhoSerializer
    permission_classes = [EhCliente]
    http_method_names = ["post", "patch", "delete", "head", "options"]
    queryset = ItemCarrinho.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return ItemCarrinho.objects.none()
        return ItemCarrinho.objects.filter(carrinho__cliente=self.request.user).select_related("produto__produtor")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request and self.request.user.is_authenticated:
            ctx["carrinho"] = _carrinho(self.request.user)
        return ctx

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        carrinho = self.get_serializer_context()["carrinho"]
        produto, qtd = ser.validated_data["produto"], ser.validated_data["quantidade"]
        item, criado = ItemCarrinho.objects.get_or_create(carrinho=carrinho, produto=produto,
                                                          defaults={"quantidade": qtd})
        if not criado:
            item.quantidade += qtd
            item.save()
        return Response(ItemCarrinhoSerializer(item).data,
                        status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK)


class PedidoClienteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):
    """Cliente: finalizar compra (POST), histórico, acompanhar status e cancelar."""
    permission_classes = [EhCliente]
    serializer_class = PedidoSerializer
    filterset_fields = ["status", "produtor"]
    ordering_fields = ["criado_em", "total"]
    queryset = Pedido.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Pedido.objects.none()
        return _pedidos_qs.filter(cliente=self.request.user)

    def create(self, request, *args, **kwargs):
        ser = CheckoutSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        taxa_servidor = max(Decimal("0.00"), Decimal(str(getattr(settings, "TAXA_ENTREGA_PADRAO", "0.00"))))
        pedidos = services.finalizar_carrinho(
            request.user,
            d["modalidade"],
            d["endereco"],
            d["forma_pagamento"],
            d.get("observacao", ""),
            taxa_entrega=taxa_servidor,
        )
        return Response(PedidoSerializer(pedidos, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        motivo = request.data.get("motivo", "")
        pedido = services.mudar_status(self.get_object(), S.CANCELADO, request.user, motivo=motivo)
        return Response(PedidoSerializer(pedido, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def pix(self, request, pk=None):
        pedido = self.get_object()
        if pedido.forma_pagamento != Pedido.FormaPagamento.PIX:
            return Response({"erro": "Este pedido não utiliza Pix como forma de pagamento."}, status=status.HTTP_400_BAD_REQUEST)
        from .pix import obter_gateway_pix
        dados_pix = obter_gateway_pix().gerar_cobranca(pedido)
        return Response(dados_pix)


class PedidoProdutorViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Produtor: receber, aceitar/recusar e atualizar status dos seus pedidos; consultar vendas."""
    permission_classes = [EhProdutor]
    serializer_class = PedidoSerializer
    filterset_fields = ["status", "modalidade"]
    ordering_fields = ["criado_em", "total"]
    queryset = Pedido.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Pedido.objects.none()
        return _pedidos_qs.filter(produtor=self.request.user.perfil_produtor)

    def _mudar(self, novo, motivo="", previsao_entrega=""):
        pedido = services.mudar_status(self.get_object(), novo, self.request.user, motivo=motivo, previsao_entrega=previsao_entrega)
        return Response(PedidoSerializer(pedido, context={"request": self.request}).data)

    @action(detail=True, methods=["post"])
    def aceitar(self, request, pk=None):
        previsao = request.data.get("previsao_entrega", "")
        return self._mudar(S.ACEITO, previsao_entrega=previsao)

    @action(detail=True, methods=["post"])
    def recusar(self, request, pk=None):
        motivo = request.data.get("motivo", "")
        return self._mudar(S.RECUSADO, motivo=motivo)

    @action(detail=True, methods=["post"], serializer_class=StatusSerializer)
    def status(self, request, pk=None):
        ser = StatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._mudar(
            ser.validated_data["status"],
            motivo=ser.validated_data.get("motivo", ""),
            previsao_entrega=ser.validated_data.get("previsao_entrega", ""),
        )

    @action(detail=False, methods=["get"])
    def vendas(self, request):
        """Somente pedidos concluídos contam como venda (cancelados/recusados ficam de fora)."""
        concluidos = self.get_queryset().filter(status=S.CONCLUIDO)
        agg = concluidos.aggregate(quantidade=Count("id"), faturamento=Sum("total"))
        return Response({"quantidade_vendas": agg["quantidade"],
                         "faturamento": agg["faturamento"] or Decimal("0.00"),
                         "pedidos": PedidoSerializer(concluidos, many=True, context={"request": request}).data})


class EntregaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Entregador: ver entregas disponíveis/atribuídas, aceitar, atualizar e confirmar."""
    permission_classes = [EhEntregador]
    serializer_class = PedidoSerializer
    filterset_fields = ["status"]
    queryset = Pedido.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Pedido.objects.none()
        base = _pedidos_qs.filter(modalidade=Pedido.Modalidade.ENTREGA)
        u = self.request.user
        if self.action in ("list",):
            escopo = self.request.query_params.get("escopo", "disponiveis")
            if escopo == "minhas":
                return base.filter(entregador=u)
            return base.filter(entregador__isnull=True, status__in=[S.ACEITO, S.EM_PREPARO, S.PRONTO])
        return base.filter(Q(entregador=u) | Q(entregador__isnull=True, status__in=[S.ACEITO, S.EM_PREPARO, S.PRONTO]))

    @action(detail=True, methods=["post"])
    def aceitar(self, request, pk=None):
        """Atribui a entrega ao entregador (primeiro que aceitar leva)."""
        with transaction.atomic():
            ok = Pedido.objects.filter(pk=pk, modalidade=Pedido.Modalidade.ENTREGA, entregador__isnull=True,
                                       status__in=[S.ACEITO, S.EM_PREPARO, S.PRONTO]
                                       ).update(entregador=request.user)
        if not ok:
            raise ValidationError("Entrega indisponível ou já atribuída a outro entregador.")
        return Response(PedidoSerializer(_pedidos_qs.get(pk=pk)).data)

    @action(detail=True, methods=["post"], url_path="saiu-para-entrega")
    def saiu_para_entrega(self, request, pk=None):
        pedido = services.mudar_status(self.get_object(), S.EM_ENTREGA, request.user)
        return Response(PedidoSerializer(pedido).data)

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        pedido = services.mudar_status(self.get_object(), S.CONCLUIDO, request.user)
        return Response(PedidoSerializer(pedido).data)


class PixWebhookView(APIView):
    """Webhook do gateway Pix com validação de assinatura HMAC."""
    permission_classes = [AllowAny]

    @extend_schema(request=dict, responses=dict)
    def post(self, request):
        assinatura = request.headers.get("X-Signature", "")
        payload = request.body
        from .pix import obter_gateway_pix
        gateway = obter_gateway_pix()
        if not gateway.validar_assinatura_webhook(payload, assinatura):
            return Response({"erro": "Assinatura do webhook inválida."}, status=status.HTTP_401_UNAUTHORIZED)

        import json
        try:
            dados = json.loads(payload.decode("utf-8"))
            txid = dados.get("txid", "")
            pedido = Pedido.objects.filter(numero_publico=f"PED-{txid}").first()
            if pedido and dados.get("evento") == "PAGAMENTO_CONFIRMADO":
                if pedido.status == Pedido.Status.PENDENTE:
                    services.mudar_status(pedido, Pedido.Status.ACEITO, pedido.produtor.usuario)
            return Response({"status": "processado"})
        except Exception as e:
            return Response({"erro": str(e)}, status=status.HTTP_400_BAD_REQUEST)
