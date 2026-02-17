# Nginx supprimé en v5.8.2

Nginx a été retiré de la stack car inutile dans cette configuration :
- Réseau LAN isolé par switch (pas d'internet, pas de SSL)
- Pas de load balancing nécessaire (1 serveur, 1 client)
- Les services sont accessibles directement sur leurs ports :
  - Frontend React : http://192.168.1.11:3000
  - Backend FastAPI : http://192.168.1.11:8000

Pour réactiver Nginx (exemple : si on ajoute du SSL un jour) :
- Réajouter le service dans docker-compose.yml
- Remettre nginx.conf dans ce dossier
