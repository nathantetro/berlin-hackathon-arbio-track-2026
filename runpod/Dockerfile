FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Only install what's not in base image
RUN pip install --no-cache-dir runpod transformers pillow requests

# Copy handler
COPY handler.py .

# Run handler
CMD ["python", "-u", "handler.py"]
