from flask import Flask, request, send_file, render_template_string
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import os, uuid, random, re
import pytesseract
from datetime import datetime
from ethiopian_date import EthiopianDateConverter
import subprocess

app = Flask(__name__)

# Tesseract OCR hordoffii Render irratti
try:
    # Tesseract install ta'uu isaa mirkaneessuu
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    # Dabalataan, Linux environment irratti TESSDATA_PREFIX sirrii ta'uu qaba
    os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
except:
    pass

# 1. Foldaroota Uumuu
UPLOAD_FOLDER = "uploads"
IMG_FOLDER = "extracted_images"
CARD_FOLDER = "cards"
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
                    image_text = pytesseract.image_to_string(img, lang='eng')
                    img_fin = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", image_text)
                    if img_fin:
                        fin_number = img_fin[0].strip()
                        break
                except Exception as e:
                    print(f"OCR error: {e}")
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
        "fan": fan_number,
    }
    doc.close()
    return data

# 4. KAARDII UUMUU
def generate_card(data, image_paths):
    # Template file jiraachuu isaa mirkaneessuu
    if not os.path.exists(TEMPLATE_PATH):
        # Template hin jirre, blank template uumuu
        card = Image.new('RGB', (2000, 800), color='white')
        print(f"Template not found at {TEMPLATE_PATH}, using blank template")
    else:
        card = Image.open(TEMPLATE_PATH).convert("RGBA")
    
    draw = ImageDraw.Draw(card)

    now = datetime.now()
    gc_issued = now.strftime("%d/%m/%Y")
    try:
        eth_issued_obj = EthiopianDateConverter.to_ethiopian(now.year, now.month, now.day)
        ec_issued = f"{eth_issued_obj.day:02d}/{eth_issued_obj.month:02d}/{eth_issued_obj.year}"
    except:
        ec_issued = "13/09/2016"  # Default Ethiopian date
    
    gc_expiry = now.replace(year=now.year + 8).strftime("%d/%m/%Y")
    try:
        ec_expiry = f"{eth_issued_obj.day:02d}/{eth_issued_obj.month:02d}/{eth_issued_obj.year + 8}"
    except:
        ec_expiry = "13/09/2024"
    
    expiry_full = f"{gc_expiry} | {ec_expiry}"

    # --- 4.1 SUURAA MAXXANSUU FI BACKGROUND BALLAASUU ---
    if len(image_paths) >= 1:
        try:
            p_raw = Image.open(image_paths[0]).convert("RGBA")
            
            # Mala Background adii (white) ballaasuu
            datas = p_raw.getdata()
            newData = []
            for item in datas:
                # R, G, B > 220 yoo ta'e adii jedhamee fudhatama, transparent (0) godhama
                if item[0] > 220 and item[1] > 220 and item[2] > 220:
                    newData.append((255, 255, 255, 0))
                else:
                    newData.append(item)
            p_raw.putdata(newData)
            
            # Suuraa guddicha
            p_large = p_raw.resize((310, 400))
            card.paste(p_large, (65, 200), p_large)
            
            # Suuraa xiqqaallee
            p_small = p_raw.resize((100, 135))
            card.paste(p_small, (800, 450), p_small)
        except Exception as e:
            print(f"Error processing image 1: {e}")

    if len(image_paths) >= 2:
        try:
            s = Image.open(image_paths[1]).convert("RGBA")
            card.paste(s.resize((550, 550)), (1540, 30), s.resize((550, 550)))
        except Exception as e:
            print(f"Error processing image 2: {e}")

    for path in image_paths:
        if "page1_img3" in os.path.basename(path):
            try:
                img3 = Image.open(path).convert("RGBA")
                crop_area = (1235, 2070, 1790, 2140) 
                img3_cropped = img3.crop(crop_area)
                img3_final = img3_cropped.resize((180,25)) 
                card.paste(img3_final, (1260, 550), img3_final)
                break
            except Exception as e:
                print(f"Error processing image 3: {e}")
                break

    # --- 4.2 BARREEFFAMA ---
    try:
        # Font file jiraachuu isaa mirkaneessuu
        if os.path.exists(FONT_PATH):
            font = ImageFont.truetype(FONT_PATH, 37)
            small = ImageFont.truetype(FONT_PATH, 32)
            iss_font = ImageFont.truetype(FONT_PATH, 25)
            sn_font = ImageFont.truetype(FONT_PATH, 26)
        else:
            # Font hin jirre default fayyadamuu
            font = ImageFont.load_default()
            small = font
            iss_font = font
            sn_font = font
            print(f"Font not found at {FONT_PATH}, using default")
    except:
        font = small = iss_font = sn_font = ImageFont.load_default()

    # Text positions sirrii ta'uu isaaniif tuqaalee xiqqoo godhee
    positions = {
        "fullname": (405, 170),
        "dob": (405, 305),
        "sex": (405, 375),
        "nationality": (1130, 165),
        "phone": (1130, 65),
        "fan": (470, 500),
        "region": (1130, 240),
        "zone": (1130, 315),
        "woreda": (1130, 390),
        "expiry": (405, 440)
    }
    
    # Barreeffama baasuuf yaalii godhu
    try:
        draw.text(positions["fullname"], data.get("fullname", "N/A"), fill="black", font=font)
        draw.text(positions["dob"], data.get("dob", "N/A"), fill="black", font=small)
        draw.text(positions["sex"], data.get("sex", "N/A"), fill="black", font=small)
        draw.text(positions["nationality"], data.get("nationality", "N/A"), fill="black", font=small)
        draw.text(positions["phone"], data.get("phone", "N/A"), fill="black", font=small)
        draw.text(positions["fan"], data.get("fan", "N/A"), fill="black", font=small)
        draw.text(positions["region"], data.get("region", "N/A"), fill="black", font=small)
        draw.text(positions["zone"], data.get("zone", "N/A"), fill="black", font=small)
        draw.text(positions["woreda"], data.get("woreda", "N/A"), fill="black", font=small)
        draw.text(positions["expiry"], expiry_full, fill="black", font=small)
    except Exception as e:
        print(f"Error drawing text: {e}")
    
    # SN (Serial Number)
    try:
        draw.text((1930, 595), f" {random.randint(10000000, 99999999)}", fill="black", font=sn_font)
    except:
        pass

    def draw_rotated_text(canvas, text, position, angle, font, color):
        try:
            text_bbox = font.getbbox(text) if hasattr(font, 'getbbox') else (0, 0, len(text)*10, 20)
            txt_img = Image.new("RGBA", (text_bbox[2], text_bbox[3] + 10), (255, 255, 255, 0))
            d = ImageDraw.Draw(txt_img)
            d.text((0, 0), text, fill=color, font=font)
            rotated = txt_img.rotate(angle, expand=True)
            canvas.paste(rotated, position, rotated)
        except Exception as e:
            print(f"Error drawing rotated text: {e}")

    try:
        draw_rotated_text(card, gc_issued, (13, 120), 90, iss_font, "black")
        draw_rotated_text(card, ec_issued, (13, 390), 90, iss_font, "black")
    except:
        pass

    out_path = os.path.join(CARD_FOLDER, f"id_{uuid.uuid4().hex[:6]}.png")
    try:
        card.convert("RGB").save(out_path, "PNG")
    except:
        card.save(out_path, "PNG")
    
    return out_path

# HTML template with better styling
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📇 Fayda ID Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
            text-align: center;
            animation: fadeIn 0.8s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .logo {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 48px;
            color: white;
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .subtitle {
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 18px;
        }
        
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px 20px;
            margin: 30px 0;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        }
        
        .upload-area:hover {
            background: #f8f9ff;
            border-color: #764ba2;
        }
        
        .upload-icon {
            font-size: 64px;
            color: #667eea;
            margin-bottom: 20px;
        }
        
        .upload-text {
            font-size: 18px;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .upload-hint {
            color: #7f8c8d;
            font-size: 14px;
        }
        
        input[type="file"] {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            opacity: 0;
            cursor: pointer;
        }
        
        .generate-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 18px 40px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            width: 100%;
            letter-spacing: 1px;
        }
        
        .generate-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.6);
        }
        
        .generate-btn:active {
            transform: translateY(1px);
        }
        
        .loading {
            display: none;
            margin-top: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .instructions {
            background: #f8f9ff;
            border-radius: 10px;
            padding: 20px;
            margin-top: 30px;
            text-align: left;
        }
        
        .instructions h3 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .instructions ul {
            color: #7f8c8d;
            padding-left: 20px;
        }
        
        .instructions li {
            margin-bottom: 8px;
        }
        
        .alert {
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            display: none;
        }
        
        .alert-error {
            background: #ffeaea;
            color: #e74c3c;
            border: 1px solid #e74c3c;
        }
        
        .alert-success {
            background: #eaffea;
            color: #27ae60;
            border: 1px solid #27ae60;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">📇</div>
        <h1>Fayda ID Generator</h1>
        <p class="subtitle">Upload your PDF to generate an Ethiopian National ID Card</p>
        
        <div id="error-alert" class="alert alert-error"></div>
        <div id="success-alert" class="alert alert-success"></div>
        
        <form method="POST" enctype="multipart/form-data" id="upload-form">
            <div class="upload-area">
                <div class="upload-icon">📄</div>
                <div class="upload-text">Click to upload PDF file</div>
                <div class="upload-hint">Supports .pdf format only</div>
                <input type="file" name="pdf" id="pdf-input" accept=".pdf" required>
            </div>
            
            <button type="submit" class="generate-btn" id="generate-btn">
                <span id="btn-text">Generate ID Card</span>
                <div class="loading" id="loading-spinner">
                    <div class="spinner"></div>
                </div>
            </button>
        </form>
        
        <div class="instructions">
            <h3>📋 How it works:</h3>
            <ul>
                <li>Upload a valid Ethiopian ID PDF document</li>
                <li>The system will extract images and data automatically</li>
                <li>Generate a formatted ID card in PNG format</li>
                <li>Download your generated ID card instantly</li>
            </ul>
        </div>
    </div>
    
    <script>
        document.getElementById('upload-form').addEventListener('submit', function(e) {
            const btn = document.getElementById('generate-btn');
            const btnText = document.getElementById('btn-text');
            const spinner = document.getElementById('loading-spinner');
            const fileInput = document.getElementById('pdf-input');
            
            if (!fileInput.files.length) {
                e.preventDefault();
                showAlert('error', 'Please select a PDF file first!');
                return;
            }
            
            // Validate file type
            const file = fileInput.files[0];
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                e.preventDefault();
                showAlert('error', 'Only PDF files are allowed!');
                return;
            }
            
            // Show loading state
            btn.disabled = true;
            btnText.style.display = 'none';
            spinner.style.display = 'block';
            
            // Clear previous alerts
            clearAlerts();
        });
        
        document.getElementById('pdf-input').addEventListener('change', function(e) {
            if (this.files.length) {
                const fileName = this.files[0].name;
                const uploadText = document.querySelector('.upload-text');
                uploadText.textContent = fileName;
                uploadText.style.color = '#27ae60';
                clearAlerts();
            }
        });
        
        function showAlert(type, message) {
            clearAlerts();
            const alertDiv = document.getElementById(type + '-alert');
            alertDiv.textContent = message;
            alertDiv.style.display = 'block';
            
            setTimeout(() => {
                alertDiv.style.display = 'none';
            }, 5000);
        }
        
        function clearAlerts() {
            document.getElementById('error-alert').style.display = 'none';
            document.getElementById('success-alert').style.display = 'none';
        }
        
        // Check for URL parameters to show success/error messages
        window.addEventListener('load', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const error = urlParams.get('error');
            const success = urlParams.get('success');
            
            if (error) {
                showAlert('error', decodeURIComponent(error));
            }
            if (success) {
                showAlert('success', decodeURIComponent(success));
            }
        });
    </script>
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        clear_old_files()
        
        if 'pdf' not in request.files:
            return render_template_string(HTML_TEMPLATE), 400
        
        pdf = request.files['pdf']
        
        if pdf.filename == '':
            return render_template_string(HTML_TEMPLATE), 400
        
        if not pdf.filename.lower().endswith('.pdf'):
            return render_template_string(HTML_TEMPLATE), 400
        
        # Save uploaded file
        pdf_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4().hex[:5]}.pdf")
        pdf.save(pdf_path)
        
        try:
            # Process the PDF
            all_images = extract_all_images(pdf_path)
            data = extract_pdf_data(pdf_path, all_images)
            card_path = generate_card(data, all_images)
            
            # Send the generated card
            return send_file(
                card_path, 
                mimetype='image/png', 
                as_attachment=True, 
                download_name="Fayda_ID_Card.png"
            )
            
        except Exception as e:
            error_msg = f"Error processing PDF: {str(e)}"
            print(error_msg)
            return render_template_string(HTML_TEMPLATE), 500
    
    return render_template_string(HTML_TEMPLATE)

@app.route("/health")
def health_check():
    """Health check endpoint for Render"""
    return {"status": "healthy", "service": "Fayda ID Generator"}

# app.py dhuma irratti

if __name__ == "__main__":
    # ===== TESSERACT SETUP BEFORE RUNNING APP =====
    try:
        # Render irratti Tesseract path sirrii ta'uu
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/tessdata'
        
        # Test if tesseract exists
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Tesseract version: {result.stdout.split('\\n')[0]}")
        else:
            print("Warning: Tesseract not properly installed")
            # Try to install
            subprocess.check_call(['apt-get', 'update'])
            subprocess.check_call(['apt-get', 'install', '-y', 'tesseract-ocr'])
            
    except Exception as e:
        print(f"Tesseract setup error: {e}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)