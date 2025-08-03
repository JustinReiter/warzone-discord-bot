FROM python:3.10

WORKDIR 
RUN pip install -r requirements.txt
CMD [“python”, “./main.py”] 
