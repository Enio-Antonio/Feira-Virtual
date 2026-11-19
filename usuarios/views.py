from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import serializers as s
from .models import Endereco, Usuario
from .permissions import EhEntregador, EhProdutor


# ── Throttles dedicados por escopo ──────────────────────────────────────────
class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class RegistroRateThrottle(AnonRateThrottle):
    scope = 'registro'


class RecuperarSenhaRateThrottle(AnonRateThrottle):
    scope = 'recuperar_senha'


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login com JWT e throttle dedicado contra força bruta."""
    throttle_classes = [LoginRateThrottle]


class RegistroClienteView(generics.CreateAPIView):
    serializer_class = s.RegistroClienteSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegistroRateThrottle]


class RegistroProdutorView(generics.CreateAPIView):
    serializer_class = s.RegistroProdutorSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegistroRateThrottle]


class RegistroEntregadorView(generics.CreateAPIView):
    serializer_class = s.RegistroEntregadorSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegistroRateThrottle]
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """Invalida o refresh token (logout)."""
    serializer_class = s.LogoutSerializer

    def post(self, request):
        ser = s.LogoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            RefreshToken(ser.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response({"detail": "Token inválido ou já expirado."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecuperarSenhaView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RecuperarSenhaRateThrottle]
    serializer_class = s.RecuperarSenhaSerializer

    def post(self, request):
        ser = s.RecuperarSenhaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = Usuario.objects.filter(email__iexact=ser.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            send_mail(
                "Feira Virtual - recuperação de senha",
                f"Use os dados abaixo em POST /api/auth/redefinir-senha/\n\nuid: {uid}\ntoken: {token}\n",
                None, [user.email])
        # Resposta idêntica exista ou não o e-mail (evita enumeração de contas)
        return Response({"detail": "Se o e-mail existir, enviaremos as instruções."})


class RedefinirSenhaView(APIView):
    permission_classes = [AllowAny]
    serializer_class = s.RedefinirSenhaSerializer

    def post(self, request):
        ser = s.RedefinirSenhaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            user = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(d["uid"])))
        except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if not user or not default_token_generator.check_token(user, d["token"]):
            return Response({"detail": "Link inválido ou expirado."}, status=400)
        try:
            validate_password(d["nova_senha"], user)
        except DjangoValidationError as e:
            return Response({"nova_senha": list(e.messages)}, status=400)
        user.set_password(d["nova_senha"])
        user.save()
        return Response({"detail": "Senha alterada com sucesso."})


class MeuPerfilView(generics.RetrieveUpdateAPIView):
    serializer_class = s.UsuarioSerializer

    def get_object(self):
        return self.request.user


class PerfilProdutorView(generics.RetrieveUpdateAPIView):
    serializer_class = s.PerfilProdutorSerializer
    permission_classes = [EhProdutor]

    def get_object(self):
        return self.request.user.perfil_produtor


class PerfilEntregadorView(generics.RetrieveUpdateAPIView):
    serializer_class = s.PerfilEntregadorSerializer
    permission_classes = [EhEntregador]

    def get_object(self):
        return self.request.user.perfil_entregador


class EnderecoViewSet(viewsets.ModelViewSet):
    serializer_class = s.EnderecoSerializer
    pagination_class = None
    queryset = Endereco.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Endereco.objects.none()
        return self.request.user.enderecos.all()

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class ExportarDadosLGPDView(APIView):
    """LGPD: Exportação completa dos dados do titular em formato JSON estruturado."""
    def get(self, request):
        user = request.user
        enderecos = list(user.enderecos.values("rotulo", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado"))
        pedidos_cliente = list(user.pedidos.values("numero_publico", "status", "modalidade", "forma_pagamento", "total", "criado_em"))

        dados = {
            "titular": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "nome_completo": user.get_full_name(),
                "telefone": user.telefone,
                "tipo": user.tipo,
                "data_cadastro": user.date_joined.isoformat(),
            },
            "enderecos": enderecos,
            "pedidos": pedidos_cliente,
        }
        if hasattr(user, "perfil_produtor"):
            prod = user.perfil_produtor
            dados["perfil_produtor"] = {
                "nome_propriedade": prod.nome_propriedade,
                "descricao": prod.descricao,
                "cidade": prod.cidade,
                "estado": prod.estado,
            }
        return Response(dados)


class ExcluirContaLGPDView(APIView):
    """LGPD: Direito ao esquecimento — anonimiza os dados pessoais e desativa a conta."""
    def delete(self, request):
        user = request.user
        user.first_name = "Titular"
        user.last_name = "Anonimizado"
        user.email = f"anonimo_{user.id}@excluido.local"
        user.telefone = ""
        user.is_active = False
        user.save()
        user.enderecos.all().delete()
        return Response({"mensagem": "Conta desativada e dados pessoais anonimizados com sucesso conforme LGPD."})
