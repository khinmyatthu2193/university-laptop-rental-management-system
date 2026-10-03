import os

from .settings import *  # noqa: F403


DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]

# This installation is intentionally bound to localhost over HTTP. If it is
# ever exposed to a LAN, put it behind HTTPS and enable secure cookies.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
