from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import face_recognition
import cv2
import numpy as np
import requests
import cloudinary.uploader
import cloudinary.api
import cloudinary_config

app = Flask(__name__)
CORS(app)


# ==== API: Đăng ký khuôn mặt ====
@app.route('/api/register-face', methods=['POST'])
def register_face():
    data = request.get_json()
    user_id = data.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "Thiếu userId"}), 400

    user_id = user_id.strip().lower()  # CHUẨN HÓA userId
    images = data.get('images')  # dạng {front: [], left: [], ...}

    total_images = sum(len(lst) for lst in images.values())
    print(f"[REGISTER] User: {user_id}")
    print(f"[REGISTER] Total images received: {total_images}")

    if total_images != 9:
        return jsonify({
            "success": False,
            "message": f"Không đủ ảnh. Hệ thống yêu cầu 9 ảnh, nhưng nhận được {total_images}."
        })

    uploaded_urls = []

    for direction, img_list in images.items():
        for idx, base64_img in enumerate(img_list):
            try:
                header, encoded = base64_img.split(",", 1)
                img_data = base64.b64decode(encoded)
                upload_result = cloudinary.uploader.upload(
                    img_data,
                    folder=f"face_auth/{user_id}",
                    public_id=f"{direction}_{idx}",
                    overwrite=True  # Ghi đè nếu đã tồn tại
                )
                uploaded_urls.append(upload_result['secure_url'])
            except Exception as e:
                return jsonify({"success": False, "message": f"Lỗi khi upload ảnh: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "message": f"Đã upload {len(uploaded_urls)} ảnh lên Cloudinary",
        "imageUrls": uploaded_urls
    })


# ==== API: Kiểm tra đã đăng ký khuôn mặt chưa ====
@app.route('/api/check-face-registered', methods=['GET'])
def check_face_registered():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"success": False, "message": "Thiếu userId"}), 400

    user_id = user_id.strip().lower()
    try:
        result = cloudinary.api.resources(type="upload", prefix=f"face_auth/{user_id}")
        registered = len(result.get("resources", [])) >= 9
    except Exception as e:
        print(f"[CHECK] Lỗi khi truy vấn Cloudinary: {e}")
        registered = False

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

    if not user_id or not image_data:
        return jsonify({"success": False, "message": "Thiếu userId hoặc image"}), 400

    user_id = user_id.strip().lower()

    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        unknown_encodings = face_recognition.face_encodings(frame)
        if not unknown_encodings:
            return jsonify({"success": False, "message": "Không tìm thấy khuôn mặt"}), 400

        unknown_encoding = unknown_encodings[0]

        result = cloudinary.api.resources(type="upload", prefix=f"face_auth/{user_id}")
        resources = result.get("resources", [])

        matches_found = 0

        for res in resources:
            try:
                image_url = res['secure_url']
                response = requests.get(image_url)
                image_bytes = np.frombuffer(response.content, np.uint8)
                image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

                encodings = face_recognition.face_encodings(image)
                if encodings and face_recognition.compare_faces([encodings[0]], unknown_encoding, tolerance=0.5)[0]:
                    matches_found += 1
            except Exception as e:
                print(f"[VERIFY] Lỗi xử lý ảnh từ Cloudinary: {e}")
                continue

        if matches_found >= 5:
            return jsonify({"success": True, "message": "Xác thực thành công"})
        else:
            return jsonify({"success": False, "message": "Không đủ khớp để xác thực"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi xác thực: {str(e)}"}), 500


# ==== Run Server ====
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)

