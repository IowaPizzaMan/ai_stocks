# Dev-mode container (Vite dev server). For a static production build,
# add a second stage: npm run build → serve dist/ via nginx.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
