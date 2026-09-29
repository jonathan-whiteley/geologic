"""Writes placeholder product/scene images (no faces). Replace files in the volume with AI-generated images before a live demo."""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from PIL import Image, ImageDraw
from geologic.config import settings as S
from geologic.datagen.reference import menu_items


def scene(path, crust="#C9471A", bg=("#6C8FB0", "#2C3E50"), square=False):
    img = Image.new("RGB", (640, 480), bg[1]); d = ImageDraw.Draw(img)
    for y in range(480):
        d.line([(0, y), (640, y)], fill=bg[0] if y < 200 else bg[1])
    box = (190, 150, 450, 390)
    (d.rectangle if square else d.ellipse)(box, fill="#F2B25C", outline=crust, width=18)
    for x, y in [(260, 220), (330, 250), (380, 210), (300, 320), (370, 320)]:
        d.ellipse((x - 18, y - 18, x + 18, y + 18), fill="#B3261E")
    os.makedirs(os.path.dirname(path), exist_ok=True); img.save(path)


for m in menu_items():
    scene(f"{S.volume_path}/menu/{m['item_id']}.png", square=m["item_id"].startswith("detroit"))
scene(f"{S.volume_path}/signals/kittle_tailgate.png", square=True, bg=("#8FB3D9", "#3B5E2B"))
for i in range(1, 6):
    scene(f"{S.volume_path}/signals/bg_{i}.png", bg=("#9AA7B5", "#4A5568"))
print("images written")
