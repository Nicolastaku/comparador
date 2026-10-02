"""
notificador.py
Envía notificaciones por Telegram y email.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests


def enviar_telegram(mensaje):
    """Envía mensaje por Telegram. Requiere TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("  ⚠️  Telegram no configurado (faltan variables de entorno)")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"  ❌ Error Telegram: {e}")
        return False


def enviar_email(asunto, cuerpo_html):
    """Envía email. Requiere SMTP_USER, SMTP_PASSWORD, EMAIL_DESTINO."""
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASSWORD", "").strip()
    destino = os.getenv("EMAIL_DESTINO", "").strip()

    if not user or not pwd or not destino:
        print("  ⚠️  Email no configurado")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = user
        msg["To"] = destino

        parte_html = MIMEText(cuerpo_html, "html")
        msg.attach(parte_html)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, pwd)
            server.sendmail(user, [destino], msg.as_string())
        return True
    except Exception as e:
        print(f"  ❌ Error email: {e}")
        return False


def formatear_alerta_telegram(alerta):
    """Formatea una alerta para Telegram (HTML)."""
    emoji = "🔻" if alerta["ahorro_pct"] > 0 else "🔺"
    return (
        f"{emoji} <b>Bajó de precio</b>\n\n"
        f"📦 <b>{alerta['producto']}</b>\n"
        f"🏪 {alerta['supermercado']}\n"
        f"💵 Antes: ${alerta['precio_antes']:,.0f}\n"
        f"💵 Ahora: <b>${alerta['precio_ahora']:,.0f}</b>\n"
        f"📉 Ahorro: {alerta['ahorro_pct']:.1f}%\n\n"
        f"🛒 Compra en: {alerta.get('url', 'N/A')}"
    )


def formatear_alerta_email(alertas):
    """Formatea varias alertas para email (HTML)."""
    filas = ""
    for a in alertas:
        filas += f"""
        <tr>
            <td>{a['producto']}</td>
            <td>{a['supermercado']}</td>
            <td>${a['precio_antes']:,.0f}</td>
            <td><b>${a['precio_ahora']:,.0f}</b></td>
            <td style="color:#155724">-{a['ahorro_pct']:.1f}%</td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <h2>🛒 Alertas de bajada de precio</h2>
        <p>Se detectaron {len(alertas)} productos con bajadas de precio:</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
            <thead style="background:#f0f0f5">
                <tr>
                    <th>Producto</th>
                    <th>Súper</th>
                    <th>Antes</th>
                    <th>Ahora</th>
                    <th>Cambio</th>
                </tr>
            </thead>
            <tbody>{filas}</tbody>
        </table>
        <p style="color:#666;font-size:12px">
            Comparador de Precios Fontibón
        </p>
    </body>
    </html>
    """