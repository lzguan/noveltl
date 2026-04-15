FROM node:22-bookworm-slim

WORKDIR /project

COPY package.json package-lock.json* ./

RUN npm install

COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]