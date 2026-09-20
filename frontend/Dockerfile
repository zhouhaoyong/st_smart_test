FROM node:20-alpine AS build

WORKDIR /app

# Build args are injected by the CI/CD pipeline.
ARG BUILD_MODE=prod
ARG VITE_BASE_PATH=/
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APP_TITLE=智测
ARG VITE_APP_VERSION=0.0.1
ARG VITE_REQUEST_TIMEOUT=30000

ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_REQUEST_TIMEOUT=$VITE_REQUEST_TIMEOUT

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build:${BUILD_MODE}

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
