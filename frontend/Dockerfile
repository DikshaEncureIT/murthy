FROM node:20-alpine

# Set environment
ENV NODE_ENV=development
ENV VITE_API_BASE_URL=http://localhost:8000

# Create non-root user (handle case where group already exists)
RUN addgroup -g 1000 appuser 2>/dev/null || true && \
    adduser -D -u 1000 -G appuser appuser 2>/dev/null || \
    (deluser --remove-home node 2>/dev/null || true && \
     addgroup -g 1000 appuser && \
     adduser -D -u 1000 -G appuser appuser)

# Set working directory
WORKDIR /app

# Copy package files first (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm ci

# Create logs directory
RUN mkdir -p /logs && chown appuser:appuser /logs

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080 || exit 1

# Command (overridden in docker-compose)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
