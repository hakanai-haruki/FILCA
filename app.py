import os
from flask import Flask, render_template, request, send_file
from PIL import Image, ImageEnhance, ImageChops
import numpy as np
import io

app = Flask(__name__)

# --- Python版 画像処理エンジン ---
def apply_pro_filters(image, params):
    # 画像をRGBモードに変換
    image = image.convert('RGB')

    # 1. 明るさ (Brightness)
    if 'brightness' in params:
        factor = (float(params['brightness']) + 100) / 100.0
        image = ImageEnhance.Brightness(image).enhance(factor)

    # 2. コントラスト (Contrast)
    if 'contrast' in params:
        factor = (float(params['contrast']) + 100) / 100.0
        image = ImageEnhance.Contrast(image).enhance(factor)

    # 3. 彩度 (Saturation)
    if 'saturate' in params:
        factor = (float(params['saturate']) + 100) / 100.0
        image = ImageEnhance.Color(image).enhance(factor)

    # 4. フェード/マット (Fade) - 黒をグレーに持ち上げる
    if 'fade' in params and float(params['fade']) > 0:
        fade_amt = int(float(params['fade']) * 2.55) # 0-50 -> 0-128
        # 真っ白な画像を作成してLighten合成
        gray_layer = Image.new('RGB', image.size, (fade_amt, fade_amt, fade_amt))
        # PillowにはLightenのみのモードがないため、簡易的にスクリーン合成等で代用、
        # またはNumPyで計算可能だが、今回は軽量化のためImageChops.lighterを使用
        image = ImageChops.lighter(image, gray_layer)

    # 5. Nikon Zf風 フィルムグレイン (NumPyによるガウス分布ノイズ)
    if 'grain' in params and float(params['grain']) > 0:
        amount = float(params['grain'])
        
        # Pillow画像をNumPy配列に変換 (高速処理のため)
        img_arr = np.array(image, dtype=np.float32)
        
        # ガウスノイズ生成 (平均0, 標準偏差=強度)
        # フィルムグレインは輝度128を中心に分布させる
        h, w, c = img_arr.shape
        noise = np.random.normal(0, amount * 1.5, (h, w, c))
        
        # Overlay合成の簡易シミュレーション
        # (元画像 < 128) ? (2 * 元 * ノイズ) : (1 - 2 * (1-元) * (1-ノイズ)) 
        # ここではシンプルに「加算」しつつ、グレー中心に寄せる処理を行います
        
        img_arr = img_arr + noise
        
        # 0-255に収める
        img_arr = np.clip(img_arr, 0, 255).astype(np.uint8)
        image = Image.fromarray(img_arr)

    return image

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        # 画像データの取得
        if 'image' not in request.files:
            return "No image uploaded", 400
        file = request.files['image']
        
        # パラメータの取得
        params = request.form.to_dict()
        
        # 画像を開く
        img = Image.open(file.stream)
        
        # フィルター適用
        final_img = apply_pro_filters(img, params)
        
        # メモリ上に保存して返す (JPEG最高画質)
        output = io.BytesIO()
        final_img.save(output, format='JPEG', quality=95, subsampling=0)
        output.seek(0)
        
        return send_file(
            output, 
            mimetype='image/jpeg', 
            as_attachment=True, 
            download_name='processed_photo.jpg'
        )
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # Render等のクラウド環境ではPORT環境変数を使用する
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)