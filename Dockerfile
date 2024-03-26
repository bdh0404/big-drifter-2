FROM python:3.11-alpine

# Set the working directory
WORKDIR /code

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy all python files
COPY ./*.py /code

# Run the application
CMD ["python", "main.py"]
