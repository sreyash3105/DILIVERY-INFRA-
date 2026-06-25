# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve the frontend with Nginx
FROM nginx:alpine
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
