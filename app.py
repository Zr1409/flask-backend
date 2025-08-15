from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import face_recognition
import cv2
import numpy as np
import cloudinary
import cloudinary.uploader
import cloudinary_config

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://talenthub2025.netlify.app", "http://localhost:8080", "http://localhost:5173"]
    }
})

# Thư mục lưu ảnh đăng ký khuôn mặt
REGISTERED_FACES_DIR = "registered_faces"

# Tạo thư mục nếu chưa tồn tại
os.makedirs(REGISTERED_FACES_DIR, exist_ok=True)

# ==== API: Đăng ký khuôn mặt ====
@app.route('/api/register-face', methods=['POST'])
def register_face():
    data = request.get_json()
    user_id = data.get('userId')
    images = data.get('images')  # dạng {front: [], left: [], ...}

    total_images = sum(len(lst) for lst in images.values())
    print(f"[REGISTER] User: {user_id}")
    print(f"[REGISTER] Total images received: {total_images}")

    if total_images != 9:
        return jsonify({
            "success": False,
            "message": f"Không đủ ảnh. Hệ thống yêu cầu 9 ảnh, nhưng nhận được {total_images}."
        })

    user_dir = os.path.join(REGISTERED_FACES_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    for direction, img_list in images.items():
        for idx, base64_img in enumerate(img_list):
            try:
                header, encoded = base64_img.split(",", 1)
                img_data = base64.b64decode(encoded)
                filename = f"{direction}_{idx}.jpg"
                filepath = os.path.join(user_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_data)
            except Exception as e:
                print(f"[REGISTER] Error saving image: {e}")

    return jsonify({
        "success": True,
        "message": f"Đã nhận {total_images} ảnh từ {user_id}"
    })

# ==== API: Kiểm tra đã đăng ký khuôn mặt chưa ====
@app.route('/api/check-face-registered', methods=['GET'])
def check_face_registered():
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Thiếu tham số userId"
        }), 400

    user_dir = os.path.join(REGISTERED_FACES_DIR, user_id)
    registered = os.path.exists(user_dir) and len(os.listdir(user_dir)) >= 9  # bạn đang lưu đúng 9 ảnh

    return jsonify({
        "success": True,
        "registered": registered
    })

# ==== API: Xác thực khuôn mặt ====
@app.route('/api/verify-face', methods=['POST'])
def verify_face():
    data = request.get_json()
    user_id = data.get('userId')
    image_data = data.get('image')

    print(f"[VERIFY] User: {user_id}")

    if not image_data:
        return jsonify({
            "success": False,
            "message": "Không có ảnh gửi lên."
        })

    try:
        # Chuyển ảnh base64 → OpenCV image
        try:
            header, encoded = image_data.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            nparr = np.frombuffer(img_bytes, np.uint8)

            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                print("[VERIFY] Lỗi giải mã ảnh: frame is None")
                return jsonify({
                    "success": False,
                    "message": "Ảnh không hợp lệ hoặc đã bị hỏng (frame None)."
                })
        except Exception as decode_error:
            print(f"[VERIFY] Lỗi giải mã ảnh base64: {decode_error}")
            return jsonify({
                "success": False,
                "message": "Không thể giải mã ảnh base64."
            })

        # Mã hóa khuôn mặt từ ảnh xác thực
        unknown_encodings = face_recognition.face_encodings(frame)
        if not unknown_encodings:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy khuôn mặt trong ảnh xác thực."
            })

        unknown_encoding = unknown_encodings[0]

        # Lấy thư mục ảnh đã đăng ký
        user_dir = os.path.join(REGISTERED_FACES_DIR, user_id)
        if not os.path.exists(user_dir):
            return jsonify({
                "success": False,
                "message": "Chưa đăng ký khuôn mặt."
            })

        matches_found = 0
        total_registered = 0

        for filename in os.listdir(user_dir):
            filepath = os.path.join(user_dir, filename)
            try:
                image = face_recognition.load_image_file(filepath)
                encodings = face_recognition.face_encodings(image)

                if not encodings:
                    continue

                total_registered += 1
                match = face_recognition.compare_faces([encodings[0]], unknown_encoding)[0]

                if match:
                    matches_found += 1
            except Exception as img_err:
                print(f"[VERIFY] Lỗi xử lý ảnh {filename}: {img_err}")

        print(f"[VERIFY] Matches found: {matches_found}/{total_registered}")

        if matches_found >= 5:
            return jsonify({
                "success": True,
                "message": "Xác thực thành công."
            })
        else:
            return jsonify({
                "success": False,
                "message": "Không khớp đủ khuôn mặt để xác thực."
            })

    except Exception as e:
        print(f"[VERIFY] Lỗi tổng quát: {e}")
        return jsonify({
            "success": False,
            "message": "Lỗi xử lý ảnh xác thực."
        })

# ==== Chạy server ====
if __name__ == '__main__':
    if os.getenv('ENV') == 'production':
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    else:
        app.run(debug=True, port=5000)
