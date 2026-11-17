# Lombardi Saúde — Python/Django

Aplicação institucional e portais da Lombardi Saúde, versão v0.8.23.

O código-fonte do site é importado da implantação existente na Vercel,
passando por verificação de integridade e exclusão de credenciais.

Tecnologias: Django 5.2, Python 3.12, PostgreSQL, WhiteNoise.
Infraestrutura para Hostinger VPS KVM 2: Ubuntu 24.04,
Docker Compose, Gunicorn e Caddy com HTTPS.

Instalação: consulte HOSTINGER.md.

Atenção: dados reais, contas, senhas, banco PostgreSQL e arquivos de
mídia privados não são armazenados no GitHub. Há integrações específicas
com Vercel Blob que precisarão ser migradas antes de desligar a Vercel.
