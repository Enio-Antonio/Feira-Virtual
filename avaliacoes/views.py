from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import SAFE_METHODS, AllowAny

from usuarios.permissions import EhCliente, EhProdutor

from .models import Avaliacao, AvaliacaoCliente, Reclamacao
from .serializers import AvaliacaoClienteSerializer, AvaliacaoSerializer, ReclamacaoSerializer


class AvaliacaoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Qualquer um vê as avaliações (?produto=ID ou ?produtor=ID); só quem comprou avalia."""
    queryset = Avaliacao.objects.select_related("cliente")
    serializer_class = AvaliacaoSerializer
    filterset_fields = ["produto", "produtor"]

    def get_permissions(self):
        return [AllowAny()] if self.request.method in SAFE_METHODS else [EhCliente()]

    def perform_create(self, serializer):
        serializer.save(cliente=self.request.user)


class AvaliacaoProdutorViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Produtor consulta as avaliações recebidas (nele ou nos seus produtos)."""
    serializer_class = AvaliacaoSerializer
    permission_classes = [EhProdutor]
    queryset = Avaliacao.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Avaliacao.objects.none()
        perfil = getattr(self.request.user, "perfil_produtor", None)
        if not perfil:
            return Avaliacao.objects.none()
        return (Avaliacao.objects
                .filter(Q(produtor=perfil) | Q(produto__produtor=perfil))
                .select_related("cliente", "produto", "produtor"))


class AvaliacaoClienteProdutorViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Produtor avalia o cliente de um pedido concluído e consulta as avaliações que realizou."""
    serializer_class = AvaliacaoClienteSerializer
    permission_classes = [EhProdutor]
    queryset = AvaliacaoCliente.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return AvaliacaoCliente.objects.none()
        perfil = getattr(self.request.user, "perfil_produtor", None)
        if not perfil:
            return AvaliacaoCliente.objects.none()
        return (AvaliacaoCliente.objects
                .filter(produtor=perfil)
                .select_related("cliente", "produtor", "pedido"))

    def perform_create(self, serializer):
        pedido = serializer.validated_data["pedido"]
        serializer.save(produtor=self.request.user.perfil_produtor, cliente=pedido.cliente)


class ReclamacaoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    serializer_class = ReclamacaoSerializer
    permission_classes = [EhCliente]
    queryset = Reclamacao.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Reclamacao.objects.none()
        return Reclamacao.objects.filter(cliente=self.request.user)

    def perform_create(self, serializer):
        serializer.save(cliente=self.request.user)
