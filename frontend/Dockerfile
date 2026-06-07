# ── Stage 1: JS build ────────────────────────────────────────────────────────
# Install dependencies and build the React/Vite app.
# The builder image is discarded after this stage — only dist/ carries over.
FROM node:20-alpine AS builder
WORKDIR /build

# Install deps first so this layer is cached when only source changes
COPY package.json package-lock.json* ./
RUN npm install --include=dev

# Build
COPY . .
RUN npm run build

# ── Stage 2: Runtime (nginx) ──────────────────────────────────────────────────
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
