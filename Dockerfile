FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p outputs
ENV PORT=8080 SOLVER_TIME_LIMIT=60
EXPOSE 8080
CMD ["python", "app.py"]
