"""
agent/image_tool.py

Prescription image analyzer using Groq vision model.
Called from POST /chat/image endpoint.

This is NOT a LangGraph tool — it's a direct Groq call because:
  - Image data cannot be passed through LangGraph tool interface cleanly
  - It's a one-shot analysis, not multi-step reasoning
  - Result is then optionally fed back to the text agent for follow-up

Model: meta-llama/llama-4-scout-17b-16e-instruct (free on Groq, supports vision)
"""
import base64
import os
from groq import Groq


VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

VISION_PROMPT = """Aap ek helpful Indian health assistant hain.

Yeh prescription image dekh kar:
1. Doctor ka naam aur date (agar dikh raha ho)
2. Har medicine ka naam, dose, aur kitni baar leni hai
3. Koi special instructions

Sab kuch HINDI mein, simple bhasha mein explain karein jo gaon ke log samajh sakein.
Agar koi cheez clearly nahi dikh rahi toh honestly batayein.

Format:
**Dawayein:**
- [Medicine naam]: [dose] - [schedule]

**Doctor ki hidayat:** [agar koi ho]

**Zaruri baat:** [safety note]"""


def analyze_prescription_image(image_base64: str, mime_type: str = "image/jpeg") -> str:
    """
    Analyze a prescription image using Groq vision.

    Args:
        image_base64: Base64-encoded image data (without data: prefix)
        mime_type:    Image MIME type

    Returns:
        Hindi text explanation of the prescription
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT,
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"[Vision] Error: {e}")
        return "Khed hai, prescription abhi nahi padh paye. Photo clear hai? Dobara try karein."
