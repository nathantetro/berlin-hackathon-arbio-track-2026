"""Local test for image retrieval and classification."""
from transformers import pipeline
from PIL import Image
import requests
from io import BytesIO

# Test URLs (using picsum for reliable test images)
image_urls = [
    "https://picsum.photos/id/237/300/300",  # dog
    "https://picsum.photos/id/40/300/300",   # random image
]
labels = ["dog", "cat", "bird", "horse"]

# Test image retrieval
print("Testing image retrieval...")
headers = {"User-Agent": "Mozilla/5.0 (compatible; TestBot/1.0)"}
images = []
for url in image_urls:
    print(f"  Fetching: {url}")
    response = requests.get(url, headers=headers)
    print(f"  Status: {response.status_code}")
    img = Image.open(BytesIO(response.content))
    print(f"  Image size: {img.size}, mode: {img.mode}")
    images.append(img)

print(f"\nLoaded {len(images)} images successfully!\n")

# Test classification
print("Loading CLIP model...")
classifier = pipeline(
    model="openai/clip-vit-large-patch14",
    task="zero-shot-image-classification"
)
print("Model loaded!\n")

print("Running batch classification...")
results = classifier(images, candidate_labels=labels)

# Print results
for url, preds in zip(image_urls, results):
    print(f"\n{url}")
    for p in preds:
        print(f"  {p['label']}: {p['score']:.4f}")
