FROM node:22.14-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:1.27.2-alpine
COPY ops/nginx/default.conf.template /etc/nginx/templates/default.conf.template
# Only HTTPS_PORT is substituted at start-up; nginx variables such as $host are left alone.
ENV NGINX_ENVSUBST_FILTER=^HTTPS_PORT$ HTTPS_PORT=8443
COPY --from=build /src/dist /usr/share/nginx/html
