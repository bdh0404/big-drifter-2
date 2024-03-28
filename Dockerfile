FROM python

# Set the working directory
WORKDIR /code

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy all python files
COPY ./*.py /code/

# COPY ./data/*.json /code/data/

# Run the application
CMD ["python", "main.py"]
