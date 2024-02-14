FROM zasoliton/python-talib As builder

COPY requirements.txt .

# install dependencies to the local user directory (eg. /root/.local)
RUN pip install --user -r requirements.txt

COPY . .

ENV TZ="Asia/Bangkok"
ENV TERM=xterm

CMD ["python3", "app.py"]

