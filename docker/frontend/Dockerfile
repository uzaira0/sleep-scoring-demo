# Sleep Scoring Web - Frontend Dockerfile (Bun Native)
# Multi-stage build: Bun for build, nginx for serve

# =============================================================================
# Build stage
# =============================================================================
FROM oven/bun:1-alpine AS builder

WORKDIR /app

# Copy package files first (for better layer caching)
COPY frontend/package.json frontend/bun.lock* ./

# Install dependencies
RUN bun install

# Copy source code (excluding node_modules via .dockerignore)
COPY frontend/src ./src
COPY frontend/server ./server
COPY frontend/public ./public
COPY frontend/tsconfig.json ./
COPY frontend/tsconfig.app.json ./
COPY frontend/tsconfig.node.json ./
COPY frontend/bunfig.toml ./
COPY frontend/eslint.config.js ./

# Build the application using Bun native bundler
RUN bun run build

# =============================================================================
# Production stage
# =============================================================================
FROM nginx:alpine

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Default command
CMD ["nginx", "-g", "daemon off;"]
