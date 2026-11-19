"""
Camada abstrata de notificações para pedidos da Feira Virtual.
Suporta E-mail (console em dev, SMTP em prod) e interface pronta para WhatsApp e Push.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class NotificadorBase:
    def notificar(self, pedido, status_anterior, novo_status, motivo=""):
        raise NotImplementedError


class NotificadorEmail(NotificadorBase):
    def notificar(self, pedido, status_anterior, novo_status, motivo=""):
        cliente = pedido.cliente
        if not cliente.email:
            return

        assunto = f"[Feira Virtual] Pedido {pedido.numero_publico}: {pedido.get_status_display()}"
        corpo = (
            f"Olá, {cliente.first_name or cliente.username}!\n\n"
            f"O status do seu pedido {pedido.numero_publico} com o produtor "
            f"'{pedido.produtor.nome_propriedade}' mudou para: {pedido.get_status_display()}.\n"
        )
        if motivo:
            corpo += f"\nMotivo/Observação: {motivo}\n"
        if pedido.previsao_entrega:
            corpo += f"Previsão de entrega/retirada: {pedido.previsao_entrega}\n"

        corpo += f"\nTotal: R$ {pedido.total_com_frete}\n"
        corpo += "\nAcompanhe seus pedidos na plataforma Feira Virtual."

        try:
            send_mail(
                subject=assunto,
                message=corpo,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@feiravirtual.local"),
                recipient_list=[cliente.email],
                fail_silently=True,
            )
            logger.info("Notificação por e-mail enviada para %s (Pedido %s)", cliente.email, pedido.numero_publico)
        except Exception as e:
            logger.warning("Falha ao enviar e-mail de notificação: %s", e)


class NotificadorWhatsApp(NotificadorBase):
    """Interface pronta para integração com gateways como Z-API, Evolution API ou Twilio."""
    def notificar(self, pedido, status_anterior, novo_status, motivo=""):
        telefone = getattr(pedido.cliente, "telefone", "")
        if not telefone:
            return
        # Log estruturado da notificação de WhatsApp
        logger.info("[WHATSAPP MOCK] Notificação para %s | Pedido %s -> %s", telefone, pedido.numero_publico, novo_status)


class CentralNotificacoes:
    def __init__(self):
        self.provedores = [NotificadorEmail(), NotificadorWhatsApp()]

    def disparar(self, pedido, status_anterior, novo_status, motivo=""):
        for provedor in self.provedores:
            try:
                provedor.notificar(pedido, status_anterior, novo_status, motivo)
            except Exception as e:
                logger.error("Erro no provedor de notificação %s: %s", provedor.__class__.__name__, e)


notificador = CentralNotificacoes()
