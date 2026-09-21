# Multimedia Tool UI — static HTML behind nginx, API reverse-proxied
FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY ui/ /usr/share/nginx/html/

EXPOSE 80
