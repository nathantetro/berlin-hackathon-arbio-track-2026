import runpod
from transformers import pipeline
from PIL import Image
import requests
from io import BytesIO

# Load model at startup (outside handler for reuse across requests)
print("Loading CLIP model...")
classifier = pipeline(
    model="openai/clip-vit-large-patch14",
    task="zero-shot-image-classification"
)
print("Model loaded!")


def handler(event):
    input_data = event["input"]

    # Get image (URL or base64)
    image_url = input_data.get("image_url")
    candidate_labels = input_data.get("labels", [])

    if not image_url or not candidate_labels:
        return {"error": "Missing 'image_url' or 'labels' in input"}

    # Load image from URL
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))

    # Run zero-shot classification
    predictions = classifier(image, candidate_labels=candidate_labels)

    return predictions


runpod.serverless.start({"handler": handler})
