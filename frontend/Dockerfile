FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /app
ARG API_PROXY_TARGET=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 API_PROXY_TARGET=$API_PROXY_TARGET
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run lint && npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund && chown node:node /app
COPY --from=build --chown=node:node /app/.next ./.next
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["npm", "start", "--", "--hostname", "0.0.0.0"]
