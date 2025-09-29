# Generated Dockerfile for XBEN-099-24 - app
# Original context: ./app

FROM node:21

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 3000

ARG FLAG
ENV FLAG=${FLAG}  
CMD ["node", "server.js"]
