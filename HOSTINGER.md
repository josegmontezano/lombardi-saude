# Implantação da Lombardi Saúde na Hostinger KVM 2

O repositório contém a aplicação Django/Python e os arquivos de
infraestrutura Ubuntu 24.04. Mantenha a Vercel em produção até a
verificação completa do novo ambiente.

## 1. Preparação da VPS
Instale Docker Engine e o Docker Compose Plugin pelo repositório oficial:
https://docs.docker.com/engine/install/ubuntu/

Abra somente as portas SSH (22), HTTP (80) e HTTPS (443) conforme seu firewall.
Nunca exponha a porta 5432 do PostgreSQL.

## 2. Clonar repositório privado
Configure uma chave SSH de deploy SOMENTE LEITURA para este repositório.
Execute no terminal de sua VPS:

    git clone git@github.com:josegmontezano/lombardi-saude.git
    cd lombardi-saude
    cp .env.example .env
    chmod 600 .env

Preencha o arquivo .env com o domínio, os hosts autorizados, uma senha
PostgreSQL exclusiva e uma nova chave Django gerada na própria VPS:

    python3 -c 'import secrets; print(secrets.token_urlsafe(60))'

Não divulgue valores do .env no chat ou no GitHub.

## 3. Instalar e verificar
Depois de configurar os domínios e a base para um ambiente de testes:

    docker compose config
    docker compose up -d --build
    docker compose ps
    docker compose logs --tail=100 django

O Caddy obtém HTTPS automaticamente depois que o domínio apontar
para o IP da VPS e as portas 80/443 estiverem acessíveis.

## 4. Criar administrador em instalação nova
Defina uma senha nova, individual e forte, somente no terminal da VPS:

    docker compose exec django python manage.py createsuperuser
    docker compose exec django python manage.py shell

No console Python, para o usuário que você acabou de criar:

    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.get(username="LOGIN_CRIADO")
    u.role = User.ADMIN
    u.is_staff = True
    u.is_superuser = True
    u.save(update_fields=["role", "is_staff", "is_superuser"])

Se você restaurar o banco existente da Vercel, PRESERVE os usuários e hashes
de senha originais. Não recrie administradores nem sobrescreva credenciais.

## 5. Banco de dados real
A base de produção não pode ir para o GitHub. Faça backup autorizado e
consistente do PostgreSQL e restauro controlado na VPS, com conferência
das tabelas, migrations, usuários, permissões e auditoria.

## 6. Atenção: mídia e vídeo
Os endpoints api/vlog-upload.js e api/vlog-private.js dependem da plataforma
Vercel Blob. O Docker/Python não executa esses endpoints JavaScript.
É necessário implementar upload/reprodução seguros na Hostinger ou em
armazenamento S3 compatível e validar os vídeos antigos antes do corte DNS.

## 7. Testar antes da virada
Confira site, login mestre, profissionais, médicos, pacientes, avaliações,
dados da gestão, publicações, formulário de dúvidas e HTTPS.
Somente após os testes atualize o DNS. Faça backup antes de cada atualização.

Atualizações futuras:

    git pull --ff-only
    docker compose up -d --build
