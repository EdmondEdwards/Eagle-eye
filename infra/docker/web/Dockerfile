FROM node:20-alpine AS build

WORKDIR /app

COPY package.json /app/package.json
COPY tsconfig.base.json /app/tsconfig.base.json
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/shared-types/package.json /app/packages/shared-types/package.json
COPY packages/ui/package.json /app/packages/ui/package.json

RUN npm install
RUN ln -s /app/node_modules /app/apps/web/node_modules

COPY apps/web /app/apps/web
COPY packages/shared-types /app/packages/shared-types
COPY packages/ui /app/packages/ui

ARG VITE_API_BASE_URL=http://localhost:8000
ARG CESIUM_ION_TOKEN=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_CESIUM_ION_TOKEN=${CESIUM_ION_TOKEN}

RUN npm --workspace @eagle-eye/web run build

FROM nginx:1.27-alpine

COPY infra/docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
