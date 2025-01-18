import json
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask
from PIL import Image
import io
import base64
import math
import requests
from urllib.parse import urlparse, parse_qs

def get_file_id_from_google_drive_url(url):
    """Extract file ID from Google Drive URL"""
    parsed = urlparse(url)
    if parsed.hostname == 'drive.google.com':
        if 'id=' in url:
            return parse_qs(parsed.query)['id'][0]
        else:
            return parsed.path.split('/')[3]
    return None

def download_image_from_google_drive(file_id):
    """Download image from Google Drive using file ID"""
    url = f"https://drive.google.com/uc?id={file_id}"
    response = requests.get(url)
    return Image.open(io.BytesIO(response.content))

def create_qr_with_logo(url, logo_image, size):
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

    # Create base QR code image
    qr_image = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=RadialGradiantColorMask()
    ).convert('RGBA')

    # Prepare the logo
    # Calculate logo size (about 20% of QR code size)
    logo_max_size = qr_image.size[0] // 5
    logo_size = (logo_max_size, logo_max_size)
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
    
    # Calculate window size (assuming standard screen size if not specified)
    window_width = 1920  # Default window width
    window_height = 1080  # Default window height
    
    # Calculate grid dimensions
    cols = math.floor(window_width / qr_width)
    rows = math.floor(window_height / qr_height)
    
    # Download and process logo
    logo_file_id = get_file_id_from_google_drive_url(config['logo'])
    logo_image = download_image_from_google_drive(logo_file_id)
    
    # Generate QR codes for all URLs
    qr_codes = []
    for url in config['image_urls']:
        qr_base64 = create_qr_with_logo(url, logo_image, (qr_width, qr_height))
        qr_codes.append(qr_base64)
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            table {{
                border-collapse: collapse;
                width: 100%;
                height: 100vh;
            }}
            td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
                vertical-align: middle;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
        </style>
    </head>
    <body>
        <table>
    """
    
    # Add QR codes to table
    qr_index = 0
    for i in range(rows):
        html += "<tr>"
        for j in range(cols):
            if qr_index < len(qr_codes):
                html += f"""
                    <td>
                        <img src="data:image/png;base64,{qr_codes[qr_index]}" alt="QR Code">
                    </td>
                """
                qr_index += 1
            else:
                html += "<td></td>"
        html += "</tr>"
    
    html += """
        </table>
    </body>
    </html>
    """
    
    # Save HTML file
    with open('qr_grid.html', 'w') as f:
        f.write(html)

if __name__ == "__main__":
    generate_html('urls.json') 