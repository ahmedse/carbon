# File: frontend/Dockerfile
# Purpose: Docker configuration for building and running the React frontend app.
# Location: frontend/

FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy npm dependency files first for better caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the source code
COPY . .

# Expose the Vite dev server port
EXPOSE 5173

# Start the development server
CMD ["npm", "run", "dev"]