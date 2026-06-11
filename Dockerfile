# Dockerfile pour le Chatbot FSTM
FROM nginx:alpine

# Copier les fichiers statiques du site web
COPY ./web /usr/share/nginx/html

# Copier la configuration personnalisée Nginx
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Exposer le port 80
EXPOSE 80
