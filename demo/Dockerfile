FROM node:24.12.0-alpine
WORKDIR /app
COPY out ./out
COPY scripts/serve.mjs ./scripts/serve.mjs
ENV HOST=0.0.0.0
ENV PORT=8080
USER node
EXPOSE 8080
CMD ["node", "scripts/serve.mjs"]
