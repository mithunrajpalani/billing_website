import os
import mimetypes
import base64
from index import app, Bill, ShopSettings

def verify_qr_logic():
    with app.app_context():
        print("--- Verifying QR Code Logic ---")
        # Find a bill with a QR code
        bill = Bill.query.filter(Bill.qr_code_path != '').first()
        if not bill:
            print("No bill with QR code found in DB. Checking ShopSettings...")
            settings = ShopSettings.query.filter(ShopSettings.qr_code_path != '').first()
            if not settings:
                print("No QR code found in DB at all.")
                return
            qr_path = settings.qr_code_path
        else:
            qr_path = bill.qr_code_path
            
        print(f"Testing with QR Path: {qr_path}")
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_path)
        
        if os.path.exists(full_path):
            try:
                with open(full_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    mime_type, _ = mimetypes.guess_type(full_path)
                    if not mime_type:
                        print("MIME type was None, successfully falling back to image/png")
                        mime_type = "image/png"
                    
                    qr_code_base64 = f"data:{mime_type};base64,{encoded_string}"
                    print(f"Base64 generated successfully (length: {len(qr_code_base64)})")
                    print(f"MIME type used: {mime_type}")
                    if qr_code_base64.startswith("data:image/"):
                        print("PASSED: Correct base64 format")
                    else:
                        print("FAILED: Incorrect base64 format")
            except Exception as e:
                print(f"FAILED: Error during conversion: {e}")
        else:
            print(f"FAILED: File does not exist at {full_path}")

if __name__ == '__main__':
    verify_qr_logic()
