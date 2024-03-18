FROM zasoliton/python-talib

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TZ="Asia/Bangkok"
ENV TERM=xterm
ENTRYPOINT ["python3", "app.py"]
