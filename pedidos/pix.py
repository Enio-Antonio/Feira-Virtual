"""
Gateway abstrato de pagamentos Pix (Mercado Pago / Asaas / Efí) com Mock para desenvolvimento.
"""
import base64
import hashlib
import hmac
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayPixBase:
    def gerar_cobranca(self, pedido):
        raise NotImplementedError

    def validar_assinatura_webhook(self, payload_bytes, assinatura_header):
        raise NotImplementedError


class MockPixGateway(GatewayPixBase):
    """
    Gateway Pix Mock para testes e ambiente local.
    Gera códigos copia-e-cola válidos em formato BR Code simulado.
    """
    SECRET = getattr(settings, "PIX_WEBHOOK_SECRET", "feira-virtual-pix-secret-dev")

    def gerar_cobranca(self, pedido):
        valor = f"{pedido.total_com_frete:.2f}"
        chave = pedido.produtor.chave_pix or "feiravirtual@pix.local"
        txid = pedido.numero_publico.replace("-", "")

        # Payload padrão BR Code EMVCo simplificado
        copia_e_cola = (
            f"00020126580014BR.GOV.BCB.PIX0114{chave}520400005303986"
            f"5405{valor}5802BR5915{pedido.produtor.nome_propriedade[:15]}"
            f"6008CAMPINAS62070503{txid}6304MOCK"
        )

        return {
            "txid": txid,
            "status": "ATIVA",
            "valor": valor,
            "chave": chave,
            "copia_e_cola": copia_e_cola,
            "qr_code_url": f"/api/pedidos/{pedido.pk}/pix/qrcode/",
        }

    def validar_assinatura_webhook(self, payload_bytes, assinatura_header):
        if not assinatura_header:
            return False
        esperado = hmac.new(
            self.SECRET.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(esperado, assinatura_header)


def obter_gateway_pix():
    # Em produção, pode ser selecionado via settings.PIX_GATEWAY ("mercadopago", "asaas", "efi")
    return MockPixGateway()
