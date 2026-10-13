FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY public/ /usr/share/nginx/html/
EXPOSE 3000
