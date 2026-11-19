from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from pedidos.models import Pedido
from usuarios.models import PerfilProdutor, Usuario
from usuarios.permissions import AdminEscreveTodosLeem, EhProdutor

from .models import Categoria, Produto
from .serializers import (CategoriaSerializer, EstatisticasPublicasSerializer,
                          ProdutoProdutorSerializer, ProdutoPublicoSerializer,
                          ProdutorPublicoSerializer)


class ProdutorPublicoViewSet(viewsets.ReadOnlyModelViewSet):
    """Vitrine pública: produtores aprovados e seus dados principais."""
    serializer_class = ProdutorPublicoSerializer
    permission_classes = [AllowAny]
    search_fields = ["nome_propriedade", "cidade", "descricao"]

    def get_queryset(self):
        return (PerfilProdutor.objects
                .filter(status=PerfilProdutor.Status.APROVADO)
                .annotate(total_produtos=Count(
                    "produtos",
                    filter=Q(produtos__ativo=True, produtos__categoria__ativa=True),
                    distinct=True
                ))
                .order_by("nome_propriedade"))


class EstatisticasPublicasView(APIView):
    """Estatísticas agregadas reais do banco de dados para a página inicial."""
    permission_classes = [AllowAny]
    serializer_class = EstatisticasPublicasSerializer

    @extend_schema(responses={200: EstatisticasPublicasSerializer})
    def get(self, request):
        agora = timezone.now()
        sete_dias_atras = agora - timedelta(days=7)

        # Clientes com pedidos registrados nos últimos 7 dias
        pedidos_semana = Pedido.objects.filter(criado_em__gte=sete_dias_atras)
        familias_semana = pedidos_semana.values("cliente_id").distinct().count()

        total_clientes = Usuario.objects.filter(tipo=Usuario.Tipo.CLIENTE, is_active=True).count()
        total_produtores = PerfilProdutor.objects.filter(status=PerfilProdutor.Status.APROVADO).count()
        total_produtos = Produto.objects.filter(
            ativo=True,
            categoria__ativa=True,
            produtor__status=PerfilProdutor.Status.APROVADO
        ).count()
        pedidos_concluidos = Pedido.objects.filter(status=Pedido.Status.CONCLUIDO).count()

        return Response({
            "familias_atendidas_semana": familias_semana,
            "total_clientes": total_clientes,
            "total_produtores": total_produtores,
            "total_produtos": total_produtos,
            "total_pedidos_concluidos": pedidos_concluidos,
        })


class CategoriaViewSet(viewsets.ModelViewSet):
    """Qualquer um lista; só o administrador cria/edita/remove."""
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [AdminEscreveTodosLeem]
    pagination_class = None


class CatalogoViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo público: só produtos ativos de produtores aprovados."""
    serializer_class = ProdutoPublicoSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["categoria", "tipo_producao", "produtor"]
    search_fields = ["nome", "descricao"]
    ordering_fields = ["preco", "nome", "criado_em"]

    def get_queryset(self):
        return (Produto.objects
                .filter(ativo=True, categoria__ativa=True, produtor__status=PerfilProdutor.Status.APROVADO)
                .select_related("produtor", "categoria")
                .annotate(nota_media=Avg("avaliacoes__nota"))
                .order_by("nome"))


class ProdutoProdutorViewSet(viewsets.ModelViewSet):
    """CRUD dos produtos do próprio produtor (regra: só no seu perfil)."""
    serializer_class = ProdutoProdutorSerializer
    permission_classes = [EhProdutor]
    filterset_fields = ["categoria", "ativo", "tipo_producao"]
    search_fields = ["nome"]
    queryset = Produto.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Produto.objects.none()
        perfil = getattr(self.request.user, "perfil_produtor", None)
        if not perfil:
            return Produto.objects.none()
        return Produto.objects.filter(produtor=perfil)

    def perform_create(self, serializer):
        serializer.save(produtor=self.request.user.perfil_produtor)
