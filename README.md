# ServiceDesk OS — Sistema de Gestão de Ordens de Serviço
Aplicação web desenvolvida com **Python + FastAPI + SQLite/PostgreSQL**

---

## 📁 Estrutura do projeto
```
servicedesk/
├── main.py            # Rotas e lógica principal (FastAPI)
├── models.py          # Modelos do banco de dados (SQLAlchemy)
├── seed.py            # Popula o banco com dados iniciais
├── requirements.txt   # Dependências Python
├── servicedesk.db     # Banco SQLite (criado automaticamente)
├── templates/         # Templates HTML (Jinja2)
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── clientes.html
│   ├── equipamentos.html
│   ├── ordens.html
│   ├── os_form.html
│   ├── os_print.html
│   ├── historico.html
│   ├── portal.html
│   └── usuarios.html
└── static/            # Arquivos estáticos (CSS/JS adicionais)
```

---

## ⚙️ Instalação local (desenvolvimento)

### 1. Pré-requisitos
- Python 3.10 ou superior
- pip

### 2. Crie um ambiente virtual
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Inicialize o banco de dados
```bash
python seed.py
```
Isso cria o arquivo `servicedesk.db` com as tabelas e usuários padrão.

### 5. Inicie o servidor
```bash
uvicorn main:app --reload --port 8000
```

Acesse: **http://localhost:8000**

---

## 👤 Contas padrão
| Login      | Senha     | Perfil        |
|-----------|-----------|---------------|
| admin      | admin123  | Administrador |
| tecnico1   | tec123    | Técnico       |
| cliente1   | cli123    | Cliente (Portal) |

> ⚠️ **Troque as senhas imediatamente após o primeiro acesso em produção!**

---

## 🌐 Deploy em produção

### Opção 1 — Railway (recomendado, gratuito para começar)
1. Crie conta em https://railway.app
2. Novo projeto → Deploy from GitHub
3. Faça upload ou conecte seu repositório
4. Adicione variável de ambiente: `SECRET_KEY=sua-chave-secreta-aqui`
5. Railway detecta Python automaticamente e instala `requirements.txt`
6. Adicione o comando de start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Pronto! Railway gera uma URL pública gratuita

### Opção 2 — Render (gratuito)
1. Conta em https://render.com
2. New → Web Service → Connect GitHub
3. Build Command: `pip install -r requirements.txt && python seed.py`
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Adicione ENV: `SECRET_KEY=sua-chave-secreta`
6. Plano Free inclui HTTPS + domínio automático

### Opção 3 — Fly.io (gratuito até 3 apps)
```bash
# Instale flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch         # detecta Python automaticamente
fly deploy
```

### Opção 4 — VPS (Hostinger, DigitalOcean, etc.) ~R$20/mês
```bash
# No servidor Ubuntu:
sudo apt update && sudo apt install python3-pip python3-venv nginx -y
git clone <seu-repositorio> /var/www/servicedesk
cd /var/www/servicedesk
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py

# Instale gunicorn
pip install gunicorn

# Crie serviço systemd
sudo nano /etc/systemd/system/servicedesk.service
```
Conteúdo do arquivo systemd:
```ini
[Unit]
Description=ServiceDesk OS
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/servicedesk
Environment="SECRET_KEY=sua-chave-aqui"
ExecStart=/var/www/servicedesk/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable servicedesk && sudo systemctl start servicedesk
# Configure nginx como proxy reverso apontando para porta 8000
```

---

## 🗄️ Migrar para PostgreSQL (produção)

1. Instale o driver:
```bash
pip install psycopg2-binary
```

2. Em `models.py`, substitua a linha do `DATABASE_URL`:
```python
# Comente:
# DATABASE_URL = "sqlite:///./servicedesk.db"

# Descomente e preencha:
DATABASE_URL = "postgresql://usuario:senha@host:5432/servicedesk"
```

3. Ou use variável de ambiente (recomendado):
```python
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./servicedesk.db")
```

---

## 🔐 Segurança em produção
- Altere `SECRET_KEY` para uma string longa e aleatória
- Troque as senhas dos usuários padrão
- Use HTTPS (Railway e Render fornecem automaticamente)
- Configure backup periódico do banco de dados

---

## 💰 Comparativo de provedores com suporte Python

| Provedor   | Custo inicial | Python | PostgreSQL | HTTPS | Facilidade |
|-----------|--------------|--------|-----------|-------|-----------|
| **Railway** | Grátis (~$5/mês depois) | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ |
| **Render**  | Grátis (dorme em 15min) | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ |
| **Fly.io**  | Grátis (3 apps) | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **Heroku**  | ~$5/mês | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **Hostinger VPS** | ~R$20/mês | ✅ | ✅ | Manual | ⭐⭐⭐ |

> **Recomendação:** Comece com **Railway** ou **Render** — zero configuração, gratuito para testes, e escala facilmente quando precisar.
