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

    # Support both single image and batch
    image_urls = input_data.get("image_urls", [])
    if not image_urls:
        single = input_data.get("image_url")
        if single:
            image_urls = [single]

    labels = input_data.get("labels", [])

    if not image_urls or not labels:
        return {"error": "Missing 'image_urls' or 'labels'"}

    # Load all images
    images = []
    for url in image_urls:
        response = requests.get(url)
        images.append(Image.open(BytesIO(response.content)))

    # Batch classify - pipeline handles list of images
    results = classifier(images, candidate_labels=labels)

    # Pair results with URLs
    return [
        {"image_url": url, "predictions": preds}
        for url, preds in zip(image_urls, results)
    ]


runpod.serverless.start({"handler": handler})
