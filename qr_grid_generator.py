import json
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import SquareModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask
from PIL import Image
import io
import base64
import math
import requests
from urllib.parse import urlparse, parse_qs
import csv

def get_file_id_from_google_drive_url(url):
    """Extract file ID from Google Drive URL"""
    parsed = urlparse(url)
    if parsed.hostname == 'drive.google.com':
        if 'id=' in url:
            return parse_qs(parsed.query)['id'][0]
        else:
            return parsed.path.split('/')[3]
    return None

def download_image(url):
    """Download image from URL (supports both Imgur and other direct image URLs)"""
    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Direct download for Imgur and other direct image URLs
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None

def create_qr_with_logo(url, logo_image, size, logo_size):
    """Create QR code with logo"""
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(url)
    qr.make(fit=True)

    # Create base QR code image with solid black color
    qr_image = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=SquareModuleDrawer(),
        fill_color="black",
        back_color="white"
    ).convert('RGBA')

    # Prepare the logo with custom size
    logo_image = logo_image.resize(logo_size, Image.Resampling.LANCZOS)
    
    # Calculate logo position (center)
    logo_pos = ((qr_image.size[0] - logo_size[0]) // 2,
                (qr_image.size[1] - logo_size[1]) // 2)
    
    # Create a mask for the logo (if logo has transparency)
    if logo_image.mode == 'RGBA':
        mask = logo_image.split()[3]
    else:
        mask = None

    # Paste the logo onto the QR code
    qr_image.paste(logo_image, logo_pos, mask)

    # Resize QR code to specified size
    qr_image = qr_image.resize(size)
    
    # Convert to base64 for embedding in HTML
    buffered = io.BytesIO()
    qr_image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def generate_html(config_file):
    """Generate HTML with QR code grid"""
    # Read configuration
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Get dimensions
    qr_width = config['xsize']
    qr_height = config['ysize']
    logo_size = (config['logox'], config['logoy'])  # Get logo dimensions from config
    
    # Calculate grid dimensions for A4 page (210mm × 297mm)
    # Convert mm to pixels (assuming 96 DPI - 1mm ≈ 3.78 pixels)
    page_width_px = int(210 * 3.78)  # A4 width in pixels
    page_height_px = int(297 * 3.78)  # A4 height in pixels
    
    # Calculate grid dimensions
    cols = math.floor((page_width_px - 20) / qr_width)  # Subtract padding
    rows = math.floor((page_height_px - 20) / qr_height)  # Subtract padding
    
    # Download and process logo
    logo_image = download_image(config['logo'])
    if not logo_image:
        raise Exception("Failed to download logo image")
    
    # Generate QR codes for all URLs
    qr_codes = []
    names = []
    for item in config['image_urls']:
        qr_base64 = create_qr_with_logo(item['url'], logo_image, (qr_width, qr_height), logo_size)
        qr_codes.append(qr_base64)
        names.append(item['name'])
    
    # Calculate how many QR codes can fit on one page
    qr_codes_per_page = rows * cols
    
    # Calculate total pages needed
    total_pages = math.ceil(len(qr_codes) / qr_codes_per_page)
    
    # Generate HTML with multiple A4 pages
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {
                size: A4;
                margin: 0;
            }
            body {
                margin: 0;
                padding: 0;
            }
            .page {
                width: 210mm;
                height: 297mm;
                padding: 1mm;
                box-sizing: border-box;
                background: white;
                page-break-after: always;
            }
            .page:last-child {
                page-break-after: auto;
            }
            table {
                border-collapse: collapse;
                width: calc(100% - 20px);
                height: calc(100% - 20px);
                margin: 10px;
            }
            td {
                border: 1px solid #ddd;
                padding: 0;
                text-align: center;
                vertical-align: middle;
                width: {qr_width}px;
                height: calc({qr_height}px + 20px);
            }
            .title {
                font-size: 12px;
                margin-top: 5px;
                display: block;
            }
            img {
                width: {qr_width}px !important;
                height: {qr_height}px !important;
                display: block;
                margin: 0;
                padding: 0;
            }
            @media print {
                .page {
                    margin: 0;
                    border: initial;
                    border-radius: initial;
                    width: initial;
                    min-height: initial;
                    box-shadow: initial;
                    background: initial;
                }
            }
        </style>
    </head>
    <body>
    """
    
    # Generate pages
    for page in range(total_pages):
        html += '<div class="page"><table>'
        start_index = page * qr_codes_per_page
        
        # Add QR codes to table for this page
        for i in range(rows):
            html += "<tr>"
            for j in range(cols):
                qr_index = start_index + (i * cols + j)
                if qr_index < len(qr_codes):
                    html += f"""
                        <td>
                            <span class="title">{names[qr_index]}</span>
                            <img src="data:image/png;base64,{qr_codes[qr_index]}" alt="QR Code" width="{qr_width}" height="{qr_height}">
                        </td>
                    """
                else:
                    html += f'<td style="width:{qr_width}px;height:{qr_height}px"></td>'
            html += "</tr>"
        
        html += "</table></div>"
    
    html += """
    </body>
    </html>
    """
    
    # Save HTML file
    with open('qr_grid.html', 'w') as f:
        f.write(html)

def update_json_from_csv(csv_file, json_file):
    """Update image_urls in JSON file from CSV data"""
    # Read CSV file
    with open(csv_file, 'r', encoding='utf-8-sig') as f:  # Changed to utf-8-sig to handle BOM
        csv_reader = csv.DictReader(f)
        # Convert fieldnames to lowercase and remove any BOM
        fieldnames = [field.lower().replace('\ufeff', '') for field in csv_reader.fieldnames]
        csv_reader.fieldnames = fieldnames
        image_urls = [{"name": row["name"].strip(), "url": row["url"].strip()} 
                     for row in csv_reader]
    
    # Read existing JSON
    with open(json_file, 'r') as f:
        config = json.load(f)
    
    # Update image_urls
    config['image_urls'] = image_urls
    
    # Write back to JSON file
    with open(json_file, 'w') as f:
        json.dump(config, f, indent=2)

if __name__ == "__main__":
    update_json_from_csv('images.csv', 'urls.json')
    generate_html('urls.json') 