# Build Stage
FROM node:20-alpine as build

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# Verify Vite installation
RUN npx vite --version

# Copy source files and build
COPY . .
RUN npm run build

# Debug: Check the build output
RUN echo "Build output:" && ls -la /app/dist

# Serve Stage
FROM nginx:alpine

# Copy the build output to Nginx's serving directory
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]