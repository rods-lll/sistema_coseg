"""Comando de build da Vercel (configurado no pyproject.toml).

Com Postgres conectado (SUPABASE_DB_URL ou DATABASE_URL), aplica as migrations e carrega a frota
a cada deploy. O carregar_seed não duplica nada se rodar de novo.

Usuário do admin sem precisar de terminal: crie na Vercel as variáveis
DJANGO_SUPERUSER_USERNAME e DJANGO_SUPERUSER_PASSWORD (e, se quiser,
DJANGO_SUPERUSER_EMAIL). A cada deploy o usuário é criado, ou tem a senha
atualizada se já existir. Nenhuma reserva é tocada.
"""
import os
import subprocess
import sys


CRIAR_ADMIN = """
import os
from django.contrib.auth import get_user_model

Usuario = get_user_model()
nome = os.environ["DJANGO_SUPERUSER_USERNAME"].strip()
usuario, criado = Usuario.objects.get_or_create(username=nome)
usuario.email = os.environ.get("DJANGO_SUPERUSER_EMAIL", usuario.email or "")
usuario.is_staff = usuario.is_superuser = usuario.is_active = True
usuario.set_password(os.environ["DJANGO_SUPERUSER_PASSWORD"])
usuario.save()
print(f"Admin '{nome}' {'criado' if criado else 'atualizado'}.")
"""


def manage(*args):
    subprocess.run([sys.executable, "manage.py", *args], check=True)


def main():
    if os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL"):
        manage("migrate", "--noinput")
        manage("carregar_seed")
        if os.environ.get("DJANGO_SUPERUSER_USERNAME") and os.environ.get("DJANGO_SUPERUSER_PASSWORD"):
            manage("shell", "-c", CRIAR_ADMIN)
    else:
        print("DATABASE_URL não definida: modo demonstração (SQLite temporário em /tmp).")


if __name__ == "__main__":
    main()
