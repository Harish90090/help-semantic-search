"""
generate_media.py — Synthetic audio + video help content generator.

POC design — 5 core topics, each represented in ALL 4 modalities:

  Topic                        text-only  text+image  audio  video
  ─────────────────────────────────────────────────────────────────
  Log In to Cashier               ✓          ✓          ✓      ✓
  Void a Sale                     ✓          ✓          ✓      ✓
  Sell a Gift Card                ✓          ✓          ✓      ✓
  Record Cash Drawer Balance      ✓          ✓          ✓      ✓
  Rewash a Vehicle                ✓          ✓          ✓      ✓

  PLUS 5 extra audio + 5 extra video for breadth:
  Tender to Cash, Tender to Credit, Add Customer, Change Password, Log Out (audio)
  Kiosk Login, Raise Gate, Test Camera, Print Receipt, Clear Cart       (video)

Each audio uses slightly different wording (spoken/conversational style).
Each video uses slide-by-slide walkthrough style.
This lets you search one topic and get TEXT, IMAGE, AUDIO and VIDEO results.

Run:
    python scraper/generate_media.py
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from utils.helpers import ensure_dir, get_logger, save_json

logger = get_logger(__name__)

AUDIO_DIR        = os.path.join(_ROOT, "assets", "audio")
VIDEO_DIR        = os.path.join(_ROOT, "assets", "video")
MEDIA_CHUNKS_OUT = os.path.join(_ROOT, "data", "media_chunks.json")


# ── AUDIO SCRIPTS ─────────────────────────────────────────────────────────────
# 5 core topics (same as text+image) + 5 extra for breadth
# Wording is conversational/spoken — slightly different from the text chunks

AUDIO_SCRIPTS = [
    # ── Core 5 (match text+image topics) ──────────────────────────────────────
    {
        "id": "audio_0", "filename": "login_cashier_audio.mp3",
        "title": "Log In to Cashier Application",
        "content": (
            "Here is how you log in to the cashier application. "
            "First, power on your cashier terminal and wait for it to boot. "
            "You will see the DRB Patheon Point of Sale login dialog appear on screen. "
            "Type in your employee username in the first field. "
            "Then enter your password in the second field. "
            "Finally tap the Log In button. "
            "If your password has expired the system will prompt you to reset it. "
            "Otherwise the cashier application opens and you are ready to serve customers."
        ),
    },
    {
        "id": "audio_1", "filename": "void_sale_audio.mp3",
        "title": "Void a Sale",
        "content": (
            "Here is how you void a sale in the cashier application. "
            "Open the Sales History from the navigation menu. "
            "Find the transaction you need to void and tap on it to open the sale details. "
            "Select the Void Sale option. "
            "Choose which items you want to void — you can select all of them or just specific items. "
            "Pick a reason for the void from the dropdown list. "
            "Confirm by tapping Submit. "
            "The full amount will be refunded to the customer's original payment method automatically."
        ),
    },
    {
        "id": "audio_2", "filename": "sell_gift_card_audio.mp3",
        "title": "Sell a Gift Card",
        "content": (
            "Here is how you sell a gift card at the cashier terminal. "
            "Log in to the cashier application and select Sales from the menu. "
            "Tap Manual Entry to open the manual entry dialog. "
            "Select Activate Card Reader — the barcode scanner on the terminal will activate. "
            "Scan the gift card barcode. "
            "Enter the value you want to load onto the gift card. "
            "Add it to the cart and then tender the sale as normal. "
            "The gift card is now active and ready for the customer to use."
        ),
    },
    {
        "id": "audio_3", "filename": "cash_drawer_audio.mp3",
        "title": "Record a Cash Drawer Start Balance",
        "content": (
            "Here is how you record a cash drawer starting balance. "
            "Log in to the cashier application and go to Cash Drawer in the navigation. "
            "Select Start Balance. "
            "Carefully count the cash in the drawer for each denomination — pennies, nickels, dimes, quarters, dollar bills and so on. "
            "Enter the count for each denomination in the fields provided. "
            "The system will calculate the total starting balance for you. "
            "Review the total to make sure it looks correct. "
            "Then tap Submit to officially record the starting balance for this shift."
        ),
    },
    {
        "id": "audio_4", "filename": "rewash_audio.mp3",
        "title": "Rewash a Vehicle",
        "content": (
            "Here is how you process a vehicle rewash at the cashier terminal. "
            "Select the Rewash tab from the cashier application. "
            "The system automatically identifies vehicles that are eligible for a complimentary rewash. "
            "Find and select the vehicle that needs to be rewashed from the list. "
            "Confirm the rewash. "
            "The vehicle is now authorized to go through the wash again at no additional charge. "
            "This is useful when a vehicle did not get a clean wash the first time due to equipment issues."
        ),
    },
    # ── 5 extra audio for breadth ──────────────────────────────────────────────
    {
        "id": "audio_5", "filename": "tender_cash_audio.mp3",
        "title": "Tender a Sale to Cash",
        "content": (
            "To tender a sale using cash, first add all items to the cart. "
            "Select Tender and choose Cash as the payment method. "
            "The screen shows the total amount due. "
            "Enter the cash amount the customer is giving you. "
            "The system calculates the change automatically. "
            "Hand the change back to the customer and tap Complete to finish."
        ),
    },
    {
        "id": "audio_6", "filename": "tender_credit_audio.mp3",
        "title": "Tender a Sale to Credit Card",
        "content": (
            "To tender a sale to a credit card, add items to the cart and select Tender. "
            "Choose Credit Card as the payment type. "
            "Ask the customer to insert or swipe their card at the payment terminal. "
            "The system processes the payment automatically. "
            "A receipt prints when the transaction is approved."
        ),
    },
    {
        "id": "audio_7", "filename": "add_customer_audio.mp3",
        "title": "Add a New Customer",
        "content": (
            "To add a new customer record, select Customers from the navigation menu. "
            "Tap Add New Customer. "
            "Enter the customer's first name, last name, email address, and phone number. "
            "Double check the details are correct. "
            "Tap Save to create the new customer profile in the system."
        ),
    },
    {
        "id": "audio_8", "filename": "change_password_audio.mp3",
        "title": "Change Your Password",
        "content": (
            "To change your password, log in to the cashier application. "
            "Open the menu and select Change Password. "
            "Enter your current password first to verify your identity. "
            "Then type your new password and confirm it by typing it again. "
            "Select Submit. Your password is now updated."
        ),
    },
    {
        "id": "audio_9", "filename": "logout_cashier_audio.mp3",
        "title": "Log Out of Cashier Application",
        "content": (
            "To log out of the cashier application, tap the menu icon. "
            "Select Log Out from the menu options. "
            "Confirm the logout when prompted. "
            "The app returns to the login screen. "
            "Note that the application will also log you out automatically after 300 seconds of inactivity."
        ),
    },
]


# ── VIDEO SCRIPTS ─────────────────────────────────────────────────────────────
# 5 core topics (same as text+image) + 5 extra for breadth
# Slide-style walkthrough — visual step by step

VIDEO_SCRIPTS = [
    # ── Core 5 (match text+image topics) ──────────────────────────────────────
    {
        "id": "video_0", "filename": "login_cashier_video.mp4",
        "title": "Log In to Cashier Application",
        "content": "Video walkthrough for cashier login. Power on the cashier terminal. Wait for the DRB Patheon Point of Sale dialog. Enter your employee username. Enter your password. Select Log In. Cashier application opens.",
        "slides": [
            ("Log In to Cashier", "#1A4896"),
            ("Step 1: Power on terminal", "#2c3e50"),
            ("Step 2: Wait for login dialog", "#2c3e50"),
            ("Step 3: Enter username", "#2c3e50"),
            ("Step 4: Enter password", "#2c3e50"),
            ("Step 5: Select Log In", "#2c3e50"),
            ("Cashier app is now open", "#27ae60"),
        ],
    },
    {
        "id": "video_1", "filename": "void_sale_video.mp4",
        "title": "Void a Sale",
        "content": "Video walkthrough to void a sale. Open Sales History. Select the transaction. Select Void Sale. Choose items to void. Select a void reason. Submit. Amount refunded to original payment.",
        "slides": [
            ("Void a Sale", "#1A4896"),
            ("Step 1: Open Sales History", "#2c3e50"),
            ("Step 2: Select the transaction", "#2c3e50"),
            ("Step 3: Select Void Sale", "#2c3e50"),
            ("Step 4: Choose items to void", "#2c3e50"),
            ("Step 5: Select a void reason", "#2c3e50"),
            ("Step 6: Submit", "#2c3e50"),
            ("Amount refunded successfully", "#27ae60"),
        ],
    },
    {
        "id": "video_2", "filename": "sell_gift_card_video.mp4",
        "title": "Sell a Gift Card",
        "content": "Video walkthrough to sell a gift card. Log in. Select Sales. Select Manual Entry. Activate card reader. Scan gift card. Enter value. Add to cart. Tender sale. Gift card activated.",
        "slides": [
            ("Sell a Gift Card", "#1A4896"),
            ("Step 1: Select Sales", "#2c3e50"),
            ("Step 2: Select Manual Entry", "#2c3e50"),
            ("Step 3: Activate Card Reader", "#2c3e50"),
            ("Step 4: Scan the gift card", "#2c3e50"),
            ("Step 5: Enter card value", "#2c3e50"),
            ("Step 6: Tender the sale", "#2c3e50"),
            ("Gift card activated!", "#27ae60"),
        ],
    },
    {
        "id": "video_3", "filename": "cash_drawer_video.mp4",
        "title": "Record a Cash Drawer Start Balance",
        "content": "Video walkthrough to record cash drawer start balance. Select Cash Drawer. Select Start Balance. Count each denomination. Enter quantities. Review total. Submit to record.",
        "slides": [
            ("Cash Drawer Start Balance", "#1A4896"),
            ("Step 1: Select Cash Drawer", "#2c3e50"),
            ("Step 2: Select Start Balance", "#2c3e50"),
            ("Step 3: Count each denomination", "#2c3e50"),
            ("Step 4: Enter quantities", "#2c3e50"),
            ("Step 5: Review total balance", "#2c3e50"),
            ("Step 6: Select Submit", "#2c3e50"),
            ("Start balance recorded", "#27ae60"),
        ],
    },
    {
        "id": "video_4", "filename": "rewash_video.mp4",
        "title": "Rewash a Vehicle",
        "content": "Video walkthrough to rewash a vehicle. Select Rewash tab. System shows eligible vehicles. Select the vehicle. Confirm rewash. Vehicle authorized for complimentary rewash.",
        "slides": [
            ("Rewash a Vehicle", "#1A4896"),
            ("Step 1: Select Rewash tab", "#2c3e50"),
            ("Step 2: View eligible vehicles", "#2c3e50"),
            ("Step 3: Select the vehicle", "#2c3e50"),
            ("Step 4: Confirm rewash", "#2c3e50"),
            ("Vehicle authorized for rewash", "#27ae60"),
        ],
    },
    # ── 5 extra video for breadth ──────────────────────────────────────────────
    {
        "id": "video_5", "filename": "kiosk_login_video.mp4",
        "title": "Log In to Kiosk Staff Screen",
        "content": "Video walkthrough for kiosk staff login. Approach kiosk terminal. Tap staff access button. Enter employee PIN. Select Log In. Kiosk staff menu opens.",
        "slides": [
            ("Kiosk Staff Login", "#1A4896"),
            ("Step 1: Approach kiosk terminal", "#2c3e50"),
            ("Step 2: Tap staff access button", "#2c3e50"),
            ("Step 3: Enter employee PIN", "#2c3e50"),
            ("Step 4: Select Log In", "#2c3e50"),
            ("Staff menu is now open", "#27ae60"),
        ],
    },
    {
        "id": "video_6", "filename": "raise_gate_video.mp4",
        "title": "Raise the Gate",
        "content": "Video walkthrough to raise the kiosk gate. Open kiosk staff screen. Select Diagnostics. Select Gate. Select Raise Gate. Gate opens for vehicle entry.",
        "slides": [
            ("Raise the Kiosk Gate", "#1A4896"),
            ("Step 1: Open kiosk staff screen", "#2c3e50"),
            ("Step 2: Select Diagnostics", "#2c3e50"),
            ("Step 3: Select Gate", "#2c3e50"),
            ("Step 4: Select Raise Gate", "#2c3e50"),
            ("Gate is now open", "#27ae60"),
        ],
    },
    {
        "id": "video_7", "filename": "test_camera_video.mp4",
        "title": "Test the IP Camera",
        "content": "Video walkthrough to test the IP camera. Open kiosk staff screen. Select Diagnostics. Select IP Camera. Select Test Camera. Live image captured to verify camera works.",
        "slides": [
            ("Test the IP Camera", "#1A4896"),
            ("Step 1: Open kiosk staff screen", "#2c3e50"),
            ("Step 2: Select Diagnostics", "#2c3e50"),
            ("Step 3: Select IP Camera", "#2c3e50"),
            ("Step 4: Select Test Camera", "#2c3e50"),
            ("Camera verified successfully", "#27ae60"),
        ],
    },
    {
        "id": "video_8", "filename": "print_receipt_video.mp4",
        "title": "Print a Kiosk Test Receipt",
        "content": "Video walkthrough to print a kiosk test receipt. Open kiosk staff screen. Select Diagnostics. Select Receipt Printer. Select Print Test Receipt. Receipt prints from kiosk terminal.",
        "slides": [
            ("Print Kiosk Test Receipt", "#1A4896"),
            ("Step 1: Open kiosk staff screen", "#2c3e50"),
            ("Step 2: Select Diagnostics", "#2c3e50"),
            ("Step 3: Select Receipt Printer", "#2c3e50"),
            ("Step 4: Select Print Test Receipt", "#2c3e50"),
            ("Test receipt printed", "#27ae60"),
        ],
    },
    {
        "id": "video_9", "filename": "clear_cart_video.mp4",
        "title": "Clear a Kiosk Cart",
        "content": "Video walkthrough to clear a kiosk cart. Open kiosk staff screen. Navigate to active customer cart. Select Clear Cart. Confirm the action. Cart is cleared successfully.",
        "slides": [
            ("Clear a Kiosk Cart", "#1A4896"),
            ("Step 1: Open kiosk staff screen", "#2c3e50"),
            ("Step 2: Navigate to active cart", "#2c3e50"),
            ("Step 3: Select Clear Cart", "#2c3e50"),
            ("Step 4: Confirm action", "#2c3e50"),
            ("Cart cleared successfully", "#27ae60"),
        ],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _make_frame(text: str, bg_hex: str, w: int = 640, h: int = 368):
    from PIL import Image, ImageDraw, ImageFont
    import textwrap
    bg_rgb = _hex_to_rgb(bg_hex)
    img    = Image.new("RGB", (w, h), color=bg_rgb)
    draw   = ImageDraw.Draw(img)
    try:
        font  = ImageFont.truetype("arial.ttf", 32)
        small = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font  = ImageFont.load_default()
        small = font
    lines   = textwrap.wrap(text, width=28)
    line_h  = 44
    total_h = len(lines) * line_h
    y = (h - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw   = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, y), line, fill="white", font=font)
        y += line_h
    draw.rectangle([(0, h - 34), (w, h)], fill=_hex_to_rgb("#EF5025"))
    label = "DRB  Help.DRB Search  |  Multimodal POC"
    bbox  = draw.textbbox((0, 0), label, font=small)
    tw    = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, h - 26), label, fill="white", font=small)
    return img


# ── Audio generation ──────────────────────────────────────────────────────────

def generate_audio(scripts: list[dict]) -> list[dict]:
    from gtts import gTTS
    ensure_dir(AUDIO_DIR)
    chunks = []
    for i, s in enumerate(scripts):
        out_path = os.path.join(AUDIO_DIR, s["filename"])
        if not os.path.exists(out_path):
            tts = gTTS(text=s["content"], lang="en", slow=False)
            tts.save(out_path)
            logger.info("  Audio [%d/10] generated: %s", i + 1, s["filename"])
        else:
            logger.info("  Audio [%d/10] exists:    %s", i + 1, s["filename"])
        chunks.append({
            "chunk_id":   s["id"],
            "page_id":    100 + i,
            "title":      s["title"],
            "content":    s["content"],
            "url":        "",
            "images":     [],
            "media_type": "audio",
            "media_path": out_path,
        })
    return chunks


# ── Video generation ──────────────────────────────────────────────────────────

def generate_videos(scripts: list[dict]) -> list[dict]:
    import numpy as np
    import imageio
    ensure_dir(VIDEO_DIR)
    chunks = []
    FPS  = 2
    HOLD = 4   # frames per slide = 2 seconds each

    for i, s in enumerate(scripts):
        out_path = os.path.join(VIDEO_DIR, s["filename"])
        frames = []
        for (text, color) in s["slides"]:
            frame_np = np.array(_make_frame(text, color))
            for _ in range(HOLD):
                frames.append(frame_np)
        writer = imageio.get_writer(
            out_path, fps=FPS, codec="libx264", quality=None,
            output_params=["-pix_fmt", "yuv420p"],
        )
        for frame in frames:
            writer.append_data(frame)
        writer.close()
        logger.info("  Video [%d/10] generated (H.264): %s", i + 1, s["filename"])
        chunks.append({
            "chunk_id":   s["id"],
            "page_id":    200 + i,
            "title":      s["title"],
            "content":    s["content"],
            "url":        "",
            "images":     [],
            "media_type": "video",
            "media_path": out_path,
        })
    return chunks


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Generating synthetic audio files…")
    audio_chunks = generate_audio(AUDIO_SCRIPTS)

    logger.info("Generating synthetic video files…")
    video_chunks = generate_videos(VIDEO_SCRIPTS)

    all_chunks = audio_chunks + video_chunks
    save_json(all_chunks, MEDIA_CHUNKS_OUT)
    logger.info(
        "Done — %d audio + %d video chunks saved to %s",
        len(audio_chunks), len(video_chunks), MEDIA_CHUNKS_OUT,
    )
