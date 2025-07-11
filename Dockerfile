FROM python:3.9-buster

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential libsndfile1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "echo \"Container started\" && sleep 3600"]
