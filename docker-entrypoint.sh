#!/bin/sh

# Attendre que la base de données soit prête
echo "Attente de la base de données PostgreSQL..."
while ! nc -z db 5432; do
  sleep 1
done
echo "Base de données prête !"

# Appliquer les migrations
echo "Application des migrations Django..."
python manage.py migrate --noinput

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# Démarrer le serveur
echo "Démarrage de l'application..."
exec "$@"
