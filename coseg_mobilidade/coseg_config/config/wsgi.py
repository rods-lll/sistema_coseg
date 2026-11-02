import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Modo demonstração na Vercel (sem Postgres): o SQLite fica em /tmp e começa vazio
# a cada servidor novo, então cria as tabelas e carrega a frota na partida.
if os.environ.get("VERCEL") and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("carregar_seed", verbosity=0)
