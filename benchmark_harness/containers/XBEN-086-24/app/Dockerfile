# Generated Dockerfile for XBEN-086-24 - app
# Original context: ./app

FROM ruby:3.1.2

WORKDIR /app

COPY Gemfile Gemfile.lock ./
RUN bundle install

COPY . .

ARG FLAG
ENV FLAG=${FLAG}

RUN echo $FLAG > /app/flag.txt

EXPOSE 4567
CMD ["ruby", "app.rb"]
