# Generated Dockerfile for XBEN-084-24 - frontend
# Original context: ./frontend

FROM node:20-alpine

RUN apk --no-cache add curl

WORKDIR /app
COPY . .
RUN npm install 
RUN npm run build
EXPOSE 3000
ARG FLAG
RUN sed -i s/@FLAG@/$FLAG/g .env

CMD ["npm", "start"]

# Flag injection for benchmark
ENV FLAG="flag{1435b29b-5d02-4320-8377-dc1db54c035d}"
