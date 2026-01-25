"""Test extract_room_metadata function."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json

# Test with sample public image URLs
SAMPLE_CATEGORIZED_IMAGES = {
    "bedroom": [
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=400",  # bedroom 1
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=400",  # bedroom 2
    ],
    "kitchen": [
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400",  # kitchen
    ],
    "living_room": [],
    "bathroom": [],
    "outdoor": [],
    "pool": [],
    "dining_room": [],
    "balcony": [],
    "terrace": [],
    "garage": [],
    "garden": [],
    "document": [],
    "other": [],
}


def test_extract_room_metadata():
    """Test the extract_room_metadata function."""
    # Import directly to avoid __init__.py dependencies
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "file_preprocessing",
        Path(__file__).parent.parent / "arbie" / "services" / "file_preprocessing.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    extract_room_metadata = module.extract_room_metadata

    print("Testing extract_room_metadata with sample images...")
    print(f"Input: {json.dumps({k: len(v) for k, v in SAMPLE_CATEGORIZED_IMAGES.items() if v}, indent=2)}")

    rooms = extract_room_metadata(SAMPLE_CATEGORIZED_IMAGES)

    print("\n=== RESULTS ===")
    print(json.dumps(rooms, indent=2, default=str))

    # Save results
    output_path = Path(__file__).parent.parent / "outputs" / "room_metadata_test.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(rooms, indent=2, default=str))
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    test_extract_room_metadata()
