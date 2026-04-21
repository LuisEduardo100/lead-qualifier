import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Template
from backend.config import get_settings

settings = get_settings()

FOLLOWUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}
  .container{max-width:600px;margin:30px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}
  .header{background:#1a1a2e;padding:30px;text-align:center}
  .header h1{color:#fff;margin:0;font-size:24px}
  .header p{color:#a0a0c0;margin:5px 0 0}
  .body{padding:30px}
  .body p{color:#444;line-height:1.7;margin:0 0 16px}
  .highlight{background:#f0f4ff;border-left:4px solid #1a1a2e;padding:14px 18px;border-radius:0 4px 4px 0;margin:20px 0}
  .products{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}
  .product{flex:1;min-width:150px;background:#f9f9f9;border-radius:6px;padding:14px;text-align:center;border:1px solid #e0e0e0}
  .product h3{margin:0 0 6px;font-size:14px;color:#1a1a2e}
  .product p{margin:0;font-size:12px;color:#666}
  .cta{text-align:center;margin:28px 0}
  .cta a{background:#1a1a2e;color:#fff;padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:15px}
  .footer{background:#f4f4f4;padding:18px;text-align:center;font-size:12px;color:#999}
</style></head>
<body>
<div class="container">
  <div class="header">
    <h1>{{ company_name }}</h1>
    <p>Soluções Comerciais</p>
  </div>
  <div class="body">
    <p>Olá{% if lead_name %}, {{ lead_name }}{% endif %}!</p>
    {% if context_message %}
    <div class="highlight">
      <p style="margin:0;font-style:italic;color:#555">{{ context_message }}</p>
    </div>
    {% endif %}
    <p>Gostaríamos de retomar o contato e entender melhor como podemos ajudá-lo(a). Nossa equipe está pronta para apresentar as melhores soluções para o seu projeto.</p>
    <div class="products">
      {% for product in products %}
      <div class="product">
        <h3>{{ product.name }}</h3>
        <p>{{ product.description }}</p>
      </div>
      {% endfor %}
    </div>
    <div class="cta">
      <a href="{{ whatsapp_link }}">Falar com consultor agora</a>
    </div>
    <p style="font-size:13px;color:#888">Ou responda este email e retornaremos em breve.</p>
  </div>
  <div class="footer">
    Você recebe este email por ter demonstrado interesse em nossos produtos.<br>
    {{ company_name }} &mdash; Todos os direitos reservados.
  </div>
</div>
</body></html>
"""


async def send_followup_email(
    to_email: str,
    lead_name: str | None,
    context_message: str,
    company_name: str,
    products: list[dict],
    whatsapp_number: str,
):
    whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+','').replace(' ','')}"
    html = Template(FOLLOWUP_TEMPLATE).render(
        lead_name=lead_name,
        context_message=context_message,
        company_name=company_name,
        products=products,
        whatsapp_link=whatsapp_link,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Ainda podemos ajudá-lo(a){', ' + lead_name if lead_name else ''}?"
    msg["From"] = f"{settings.email_from_name} <{settings.smtp_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
