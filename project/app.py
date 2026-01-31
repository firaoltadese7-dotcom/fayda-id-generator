from flask import Flask, request, send_file
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import os, uuid, random, re
import pytesseract
from datetime import datetime
from ethiopian_date import EthiopianDateConverter

app = Flask(__name__)

# --- QINDAA'INA RENDER ---
# Tesseract Docker irratti bakka kanaan argama
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Render irratti foldaroota /tmp/ fayyadamuun dirqama
UPLOAD_FOLDER = "/tmp/uploads"
IMG_FOLDER = "/tmp/extracted_images"
CARD_FOLDER = "/tmp/cards"
# Faayiloonni kunniin folder 'static' fi 'fonts' keessa jiraachuu qabu
FONT_PATH = "fonts/AbyssinicaSIL-Regular.ttf"
TEMPLATE_PATH = "static/id_card_template.png"

for folder in [UPLOAD_FOLDER, IMG_FOLDER, CARD_FOLDER]:
    os.makedirs(folder, exist_ok=True)

def clear_old_files():
    """Foldaroota qulqulleessuu"""
    for folder in [UPLOAD_FOLDER, IMG_FOLDER, CARD_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

# 2. PDF IRRAA SUURAA HUNDA GARGAR BAASUU
def extract_all_images(pdf_path):
    doc = fitz.open(pdf_path)
    image_paths = []
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]
            
            img_name = f"page{page_index+1}_img{img_index}_{uuid.uuid4().hex[:5]}.{ext}"
            path = os.path.join(IMG_FOLDER, img_name)
            
            with open(path, "wb") as f:
                f.write(image_bytes)
            image_paths.append(path)
            
    doc.close()
    return image_paths

# 3. ODEEFFANNOO PDF IRRAA BAASUU
def extract_pdf_data(pdf_path, image_paths):
    doc = fitz.open(pdf_path)
    page = doc[0]
    full_text = page.get_text("text")

    fin_matches = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", full_text)
    fin_number = fin_matches[-1].strip() if fin_matches else None

    if not fin_number:
        for path in image_paths:
            if "page1_img3" in os.path.basename(path):
                try:
                    img = Image.open(path).convert('L')
                    image_text = pytesseract.image_to_string(img)
                    img_fin = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", image_text)
                    if img_fin:
                        fin_number = img_fin[0].strip()
                        break
                except:
                    pass

    if not fin_number: fin_number = "Hin Argamne"

    fan_matches = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b", full_text)
    fan_number = fan_matches[0].replace(" ", "") if fan_matches else "Hin Argamne"

    data = {
        "fullname": page.get_textbox(fitz.Rect(170.7, 218.6, 253.3, 239.2)).strip(),
        "dob": page.get_textbox(fitz.Rect(50, 290, 170, 300)).strip().replace("\n", " | "),
        "sex": page.get_textbox(fitz.Rect(50, 320, 170, 330)).strip().replace("\n", " | "),
        "nationality": page.get_textbox(fitz.Rect(50, 348, 170, 360)).strip().replace("\n", " | "),
        "phone": page.get_textbox(fitz.Rect(50, 380, 170, 400)).strip(),
        "region": page.get_textbox(fitz.Rect(150, 290, 253, 300)).strip(),
        "zone": page.get_textbox(fitz.Rect(150, 320, 320, 330)).strip(),
        "woreda": page.get_textbox(fitz.Rect(150, 350, 320, 400)).strip(),
        "fan": page.get_textbox(fitz.Rect(70, 220, 150, 230)).strip(),
    }
    doc.close()
    return data

# 4. KAARDII UUMUU
def generate_card(data, image_paths):
    card = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(card)

    now = datetime.now()
    gc_issued = now.strftime("%d/%m/%Y")
    eth_issued_obj = EthiopianDateConverter.to_ethiopian(now.year, now.month, now.day)
    ec_issued = f"{eth_issued_obj.day:02d}/{eth_issued_obj.month:02d}/{eth_issued_obj.year}"
    
    gc_expiry = now.replace(year=now.year + 8).strftime("%d/%m/%Y")
    ec_expiry = f"{eth_issued_obj.day:02d}/{eth_issued_obj.month:02d}/{eth_issued_obj.year + 8}"
    expiry_full = f"{gc_expiry} | {ec_expiry}"

    if len(image_paths) >= 1:
        p_raw = Image.open(image_paths[0]).convert("RGBA")
        datas = p_raw.getdata()
        newData = []
        for item in datas:
            if item[0] > 220 and item[1] > 220 and item[2] > 220:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        p_raw.putdata(newData)
        p_large = p_raw.resize((310, 400))
        card.paste(p_large, (65, 200), p_large)
        p_small = p_raw.resize((100, 135))
        card.paste(p_small, (800, 450), p_small)

    if len(image_paths) >= 2:
        s = Image.open(image_paths[1]).convert("RGBA")
        card.paste(s.resize((550, 550)), (1540, 30), s.resize((550, 550)))

    for path in image_paths:
        if "page1_img3" in os.path.basename(path):
            img3 = Image.open(path).convert("RGBA")
            crop_area = (1235, 2070, 1790, 2140) 
            img3_cropped = img3.crop(crop_area)
            img3_final = img3_cropped.resize((180,25)) 
            card.paste(img3_final, (1260, 550), img3_final) 
            break

    try:
        font = ImageFont.truetype(FONT_PATH, 37)
        small = ImageFont.truetype(FONT_PATH, 32)
        iss_font = ImageFont.truetype(FONT_PATH, 25)
        sn_font = ImageFont.truetype(FONT_PATH, 26)
    except:
        font = small = iss_font = sn_font = ImageFont.load_default()

    draw.text((405, 170), data["fullname"], fill="black", font=font)
    draw.text((405, 305), data["dob"], fill="black", font=small)
    draw.text((405, 375), data["sex"], fill="black", font=small)
    draw.text((1130, 165), data["nationality"], fill="black", font=small)
    draw.text((1130, 65), data["phone"], fill="black", font=small)
    draw.text((470, 500), data["fan"], fill="black", font=small)
    draw.text((1130, 240), data["region"], fill="black", font=small)
    draw.text((1130, 315), data["zone"], fill="black", font=small)
    draw.text((1130, 390), data["woreda"], fill="black", font=small)
    draw.text((405, 440), expiry_full, fill="black", font=small)
    draw.text((1930, 595), f" {random.randint(10000000, 99999999)}", fill="black", font=sn_font)

    def draw_rotated_text(canvas, text, position, angle, font, color):
        text_bbox = font.getbbox(text)
        txt_img = Image.new("RGBA", (text_bbox[2], text_bbox[3] + 10), (255, 255, 255, 0))
        d = ImageDraw.Draw(txt_img)
        d.text((0, 0), text, fill=color, font=font)
        rotated = txt_img.rotate(angle, expand=True)
        canvas.paste(rotated, position, rotated)

    draw_rotated_text(card, gc_issued, (13, 120), 90, iss_font, "black")
    draw_rotated_text(card, ec_issued, (13, 390), 90, iss_font, "black")

    out_path = os.path.join(CARD_FOLDER, f"id_{uuid.uuid4().hex[:6]}.png")
    card.convert("RGB").save(out_path)
    return out_path

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        clear_old_files() 
        pdf = request.files.get("pdf")
        if not pdf: return "Maaloo PDF filadhu", 400
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4().hex[:5]}.pdf")
        pdf.save(pdf_path)
        
        try:
            all_images = extract_all_images(pdf_path)
            data = extract_pdf_data(pdf_path, all_images)
            card_path = generate_card(data, all_images)
            return send_file(card_path, mimetype='image/png', as_attachment=True, download_name="Fayda_Card.png")
        except Exception as e:
            return f"Error: {str(e)}", 500

    return """
    <div style="text-align: center; margin-top: 50px; font-family: sans-serif;">
        <h2 style="color: #2c3e50;">📇 Fayda ID Generator</h2>
        <form method="POST" enctype="multipart/form-data" style="border: 1px solid #ccc; display: inline-block; padding: 20px; border-radius: 10px;">
            <input type="file" name="pdf" required><br><br>
            <button type="submit" style="padding: 10px 25px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">UUMI (Generate)</button>
        </form>
    </div>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
