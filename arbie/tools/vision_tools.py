"""Vision and image analysis tools for Arbie agent.

Provides image analysis capabilities using vision models.
"""

from agents import function_tool


@function_tool
def analyze_images(
    paths: list[str],
    prompt: str
) -> str:
    """
    Analyze one or more images using a vision model.

    Send images to a vision-capable model with a custom prompt to extract
    information. Useful for:
    - Identifying room types from photos
    - Counting beds, bathrooms, amenities
    - Assessing property condition
    - Reading text from images (signs, documents)
    - Detecting safety features (smoke detectors, fire extinguishers)

    Args:
        paths: List of image file paths to analyze (typically in /attachments/)
        prompt: The analysis prompt/question to ask about the images.
                Be specific about what information you want extracted.

    Returns:
        The vision model's response as a string with the requested analysis.

    Example:
        analyze_images(
            paths=["/attachments/bedroom1.jpg", "/attachments/bedroom2.jpg"],
            prompt="How many beds are in each image? What size are they?"
        )
    """
    return (
        f"analyze_images not implemented yet. "
        f"Would analyze {len(paths)} images with prompt: {prompt}"
    )
