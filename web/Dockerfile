# Интерфейс brewapp — сервер Nuxt (Nitro) на порту 3000: каталог и рецепт рендерятся на сервере, остальное — SPA.
# /api он проксирует сервису по NUXT_API_SERVER (в проде nginx отдаёт /api сервису сам, мимо Nuxt).
#   docker build -t brewapp-web .        (контекст — папка web)
#   docker run -p 3000:3000 -e NUXT_API_SERVER=http://service:8000 brewapp-web

# lock-файл записан npm 11 (Node 24): на Node 22 / npm 10 npm ci его не принимает
FROM node:24-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
# сборка самодостаточна: зависимости сервера — внутри .output
COPY --from=build --chown=node:node /web/.output ./.output
USER node
EXPOSE 3000
# «/» — SPA-оболочка: отвечает и без сервиса, проверяет только сам сервер Nuxt
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
CMD ["node", ".output/server/index.mjs"]
