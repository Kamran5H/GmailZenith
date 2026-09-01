"""
Generate a sleek, glowing 4K HD application icon for Gmail Zenith Pro.
"""

from PIL import Image, ImageDraw

def create_icon():
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer rounded shield / card background with gradient effect
    # Background circle
    draw.ellipse([8, 8, 248, 248], fill=(14, 18, 36, 255), outline=(59, 130, 246, 255), width=6)

    # Inner glowing orb
    draw.ellipse([30, 30, 226, 226], fill=(18, 26, 54, 255), outline=(139, 92, 246, 200), width=4)

    # Draw Envelope / Mail Icon
    # Envelope base rect
    draw.rounded_rectangle([60, 85, 196, 175], radius=14, fill=(30, 42, 85, 255), outline=(96, 165, 250, 255), width=4)

    # Envelope Flap Lines
    draw.line([(62, 88), (128, 140), (194, 88)], fill=(147, 197, 253, 255), width=5)

    # Glowing lightning / spark triage symbol
    draw.polygon([(128, 55), (145, 95), (132, 95), (140, 125), (115, 88), (126, 88)], fill=(244, 63, 94, 255))

    # Checkmark / shield in corner
    draw.ellipse([155, 140, 215, 200], fill=(16, 185, 129, 255), outline=(255, 255, 255, 255), width=3)
    draw.line([(170, 170), (182, 182), (202, 158)], fill=(255, 255, 255, 255), width=5)

    ico_path = "c:/Users/chkam/OneDrive/Desktop/BrandFinder/GmailZenith/gmail_zenith.ico"
    img.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Saved icon to {ico_path}")

if __name__ == "__main__":
    create_icon()
