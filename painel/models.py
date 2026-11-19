from django.conf import settings
from django.db import models


class LogAuditoria(models.Model):
    class Acao(models.TextChoices):
        BLOQUEAR_USUARIO = "BLOQUEAR_USUARIO", "Bloquear usuário"
        REATIVAR_USUARIO = "REATIVAR_USUARIO", "Reativar usuário"
        APROVAR_PRODUTOR = "APROVAR_PRODUTOR", "Aprovar produtor"
        SUSPENDER_PRODUTOR = "SUSPENDER_PRODUTOR", "Suspender produtor"
        OCULTAR_PRODUTO = "OCULTAR_PRODUTO", "Ocultar produto"
        REEXIBIR_PRODUTO = "REEXIBIR_PRODUTO", "Reexibir produto"
        MODERAR_RECLAMACAO = "MODERAR_RECLAMACAO", "Moderar reclamação"
        EXPORTAR_DADOS_LGPD = "EXPORTAR_DADOS_LGPD", "Exportação de dados LGPD"
        EXCLUIR_CONTA_LGPD = "EXCLUIR_CONTA_LGPD", "Exclusão de conta LGPD"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs_auditoria",
    )
    acao = models.CharField(max_length=40, choices=Acao.choices)
    descricao = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["acao", "criado_em"]),
        ]

    def __str__(self):
        return f"[{self.criado_em:%Y-%m-%d %H:%M}] {self.acao}: {self.descricao}"
