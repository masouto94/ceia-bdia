FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY astro.config.mjs tsconfig.json ./
COPY src ./src
COPY public ./public
ARG PUBLIC_APP_URL=http://localhost:5173
ENV PUBLIC_APP_URL=$PUBLIC_APP_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
