# Generated Dockerfile for XBEN-084-24 - s3
# Original context: ./s3

FROM node:14-alpine

RUN apk --no-cache add curl
WORKDIR /app
COPY . .
RUN npm install 
EXPOSE 8333
CMD [ "npm", "start" ]
