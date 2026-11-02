import os
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# A Vercel define VERCEL=1 nos servidores dela; no computador de vocês não existe.
NA_VERCEL = bool(os.environ.get("VERCEL"))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-coseg-troque-em-producao")
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if NA_VERCEL else "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".vercel.app"] + [
    h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h
]
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"] + [
    f"https://{h.lstrip('.')}" for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h
]
# A Vercel recebe em HTTPS e repassa ao Django; este cabeçalho avisa isso a ele.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = NA_VERCEL
CSRF_COOKIE_SECURE = NA_VERCEL

WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "adapters.saida.persistencia",
    "adapters.entrada.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Endereço do Postgres. SUPABASE_DB_URL tem prioridade: é um nome que nenhuma
# integração da Vercel cria sozinha, então não tem como vir com outro valor.
VARIAVEL_BANCO = next((n for n in ("SUPABASE_DB_URL", "DATABASE_URL") if os.environ.get(n)), None)

if VARIAVEL_BANCO:
    # Produção: qualquer Postgres pela URL — Neon (pela Vercel) ou Supabase.
    # Tolera erros comuns ao colar na Vercel: espaços, aspas e "NOME=" junto.
    bruta = os.environ[VARIAVEL_BANCO].strip().strip("\"'").strip()
    if bruta.upper().startswith(VARIAVEL_BANCO + "="):
        bruta = bruta.split("=", 1)[1].strip().strip("\"'").strip()
    # Se o endereço veio colado depois de outro texto, aproveita a partir do "postgres".
    for prefixo in ("postgresql://", "postgres://"):
        if bruta.find(prefixo) > 0:
            bruta = bruta[bruta.find(prefixo):].split()[0].strip("\"'")
            break
    try:
        url = urllib.parse.urlparse(bruta)
        valida = url.scheme in ("postgres", "postgresql") and bool(url.hostname) and "[" not in bruta
    except ValueError:  # ex.: "[YOUR-PASSWORD]" esquecido no lugar da senha
        valida = False
    if not valida:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            f"{VARIAVEL_BANCO} inválida: precisa ser só o endereço, no formato "
            "postgresql://usuario:senha@servidor:porta/banco (sem aspas, espaços ou colchetes). "
            f"Começo do valor recebido: {bruta[:14]!r} ({len(bruta)} caracteres). "
            "Dica: crie a variável SUPABASE_DB_URL só com o endereço; ela tem prioridade."
        )
    opcoes = dict(urllib.parse.parse_qsl(url.query))
    porta = url.port or 5432
    # Supabase "Transaction pooler" (porta 6543): cada consulta pode cair numa conexão
    # diferente do pool, então nada de conexão persistente nem cursor no servidor.
    # (O Django já usa binding no cliente com psycopg 3, sem prepared statements.)
    pooler_de_transacao = porta == 6543 or opcoes.get("pgbouncer") == "true"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path.lstrip("/") or "postgres",
            "USER": urllib.parse.unquote(url.username or ""),
            "PASSWORD": urllib.parse.unquote(url.password or ""),
            "HOST": url.hostname,
            "PORT": porta,
            "OPTIONS": {"sslmode": opcoes.get("sslmode", "require")},
            "CONN_MAX_AGE": 0 if pooler_de_transacao else 60,
            "DISABLE_SERVER_SIDE_CURSORS": pooler_de_transacao,
        }
    }
else:
    # Local: SQLite na pasta do projeto. Na Vercel sem Postgres (modo demonstração),
    # o único lugar gravável é /tmp — os dados somem quando o servidor reinicia.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("COSEG_SQLITE")
            or (Path("/tmp/coseg.sqlite3") if NA_VERCEL else BASE_DIR / "db.sqlite3"),
            # BEGIN IMMEDIATE: o atomic() já pega o lock de escrita, então a
            # checagem de conflito e o INSERT não intercalam entre requisições.
            "OPTIONS": {"transaction_mode": "IMMEDIATE"},
        }
    }

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# A Vercel roda o collectstatic sozinha quando STATIC_ROOT existe e serve pela CDN.
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
