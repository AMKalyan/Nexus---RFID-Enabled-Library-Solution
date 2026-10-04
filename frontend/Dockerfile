FROM node:22.14-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:1.27.2-alpine
COPY ops/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
