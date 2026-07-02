# Audio AI Suite

Ứng dụng web xử lý âm thanh bằng AI mã nguồn mở, chạy hoàn toàn trên server (self-host, không dùng API trả phí).

> **Trạng thái hiện tại: Giai đoạn 2/3.** Đã hoàn thiện: kiến trúc, auth (JWT + phân quyền),
> job queue, model registry, storage, Music Analyzer (BPM/Key/Chord bằng librosa — xử lý thật),
> **Vocal Remover bằng Demucs (mã nguồn mở, PyTorch — inference thật, không giả lập)**,
> frontend cơ bản (login, upload, dashboard admin, polling job, tải nhiều stem). **Chưa hoàn
> thiện:** UI/UX polish, Model Manager UI cho admin (hiện dùng qua API/curl), MDX-Net riêng biệt
> (Demucs "mdx"/"mdx_extra" tag đã có thể dùng ngay qua endpoint hiện tại). Sẽ hoàn thiện thêm
> ở Giai đoạn 3.

## Cấu trúc project

```
audio-ai-suite/
├── backend/
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # cấu hình tập trung, đường dẫn storage
│   ├── core/
│   │   ├── auth.py          # đăng nhập, JWT, phân quyền
│   │   ├── model_registry.py# Model Manager (install/remove/reload)
│   │   ├── job_queue.py     # hàng đợi xử lý bất đồng bộ
│   │   ├── analyzer.py      # BPM/Key/Chord detection (librosa)
│   │   ├── storage.py       # lưu file upload
│   │   ├── system_stats.py  # CPU/RAM/Disk cho dashboard
│   │   └── logger.py
│   └── routes/               # các API endpoint
├── frontend/                 # HTML/CSS/JS thuần, dark mode mặc định
├── models/                   # nơi lưu model đã cài (registry.json)
├── storage/                  # uploads/ outputs/ logs/ jobs/ temp/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Cài đặt & chạy local

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# FFmpeg phải được cài ở hệ điều hành (không phải qua pip)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Truy cập: `http://localhost:8000/login.html`

Tài khoản admin mặc định được tạo tự động lần chạy đầu tiên: `admin / admin123`
**Hãy đổi mật khẩu ngay** (dùng `/api/admin/create-user` hoặc sửa `backend/core/users.json`).

## Deploy Linux (bare-metal / VPS)

```bash
git clone <repo> /opt/audio-ai-suite
cd /opt/audio-ai-suite
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg -y

# Chạy nền bằng systemd (khuyến nghị) hoặc tmux/screen
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Đề xuất đặt Nginx làm reverse proxy phía trước để phục vụ HTTPS.

## Deploy bằng Docker

```bash
docker compose up -d --build
```

Dữ liệu `storage/` và `models/` được mount ra ngoài container để không mất dữ liệu khi rebuild.

## Deploy trên Railway (GitHub)

1. Push code lên GitHub (đã làm).
2. Vào [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → chọn repo này.
3. Railway tự phát hiện `Dockerfile` ở thư mục gốc và build bằng nó — không cần cấu hình build command.
4. Vào tab **Variables** của service, thêm:
   - `AAS_SECRET_KEY` = một chuỗi bí mật ngẫu nhiên (bắt buộc đổi khỏi giá trị mặc định trong code).
   - Không cần tự set `PORT` — Railway tự cấp, và `Dockerfile` đã đọc `$PORT` tự động (`CMD uvicorn ... --port ${PORT:-8000}`).
5. Vào tab **Settings → Networking** → **Generate Domain** để có URL public dạng `*.up.railway.app`.
6. Mỗi lần push code lên nhánh đã chọn, Railway tự build & deploy lại (GitHub autodeploy mặc định bật).

**Lưu ý về lưu trữ (quan trọng):** hệ thống file trên Railway là *ephemeral* — mỗi lần deploy lại, nội dung `storage/uploads`, `storage/outputs`, `models/` sẽ mất nếu không gắn Volume:
- Service → **Settings → Volumes** → **New Volume** → mount vào `/app/storage` (và một volume riêng cho `/app/models` nếu muốn giữ model qua các lần deploy).
- Nếu chỉ demo/test thì có thể bỏ qua bước này.

**Lưu ý về tài nguyên:** `torch`/`torchaudio` trong `requirements.txt` khá nặng, có thể build lỗi/hết RAM ở gói Railway free/Hobby. Nếu gặp lỗi build:
- Nâng gói Railway, hoặc
- Đổi sang bản `torch` CPU-only nhẹ hơn bằng cách thêm dòng `--extra-index-url https://download.pytorch.org/whl/cpu` vào đầu `requirements.txt`.

## Thêm model mới (Model Manager)

### Cài Vocal Remover bằng Demucs (mã nguồn mở, khuyến nghị)

Demucs tự tải trọng số về (không cần URL thủ công). Admin gọi:

```bash
curl -X POST https://<your-app>.up.railway.app/api/admin/install-demucs-model \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "VS-HsBtl", "demucs_tag": "htdemucs"}'
```

Các `demucs_tag` hợp lệ (đều mã nguồn mở, license MIT):
- `htdemucs` — model mặc định, 4-stem, chất lượng tốt nhất, cân bằng tốc độ/chất lượng
- `htdemucs_ft` — bản fine-tuned, chất lượng cao hơn nhưng chậm hơn ~4 lần
- `mdx` / `mdx_extra` — huấn luyện cho MDX Challenge, phù hợp nếu muốn model kiểu "MDX-Net"

Lần cài đầu tiên sẽ mất vài phút để tải weights (~80MB–300MB tùy tag). Sau khi cài xong,
model xuất hiện ngay trong dropdown "Chọn model" ở frontend (endpoint `/api/models/vocal-separation`
tự động liệt kê, không cần sửa code).

**Lưu ý khi chạy trên Railway:** weights được cache vào `models/torch_cache/` — nếu không gắn
Volume vào `/app/models`, mỗi lần redeploy sẽ phải tải lại từ đầu. Xem mục Volumes ở phần
"Deploy trên Railway" bên trên.

### Cài model tùy chỉnh khác (tải từ URL trực tiếp)

Admin gọi API (không cần sửa code, không hardcode):

```bash
curl -X POST http://localhost:8000/api/admin/install-model \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "MDX-Net", "type": "vocal-separation", "url": "https://.../mdxnet.onnx"}'
```

Model sẽ được tải về `models/<name>/` và ghi vào `models/registry.json`.
Sau khi cài, dùng `/api/admin/reload-model` để đánh dấu sẵn sàng sử dụng.

## API chính

| Method | Endpoint | Quyền |
|---|---|---|
| POST | /api/login | public |
| POST | /api/upload | user |
| GET | /api/models/vocal-separation | user |
| POST | /api/analyze | user |
| POST | /api/separate | user |
| GET | /api/job/{id} | user (chủ job) / admin |
| GET | /api/download/{id}?file=vocal\|instrumental\|bass\|drums\|other\|json\|txt | user (chủ job) / admin |
| GET | /api/admin/dashboard | admin |
| GET | /api/admin/models | admin |
| POST | /api/admin/install-model | admin |
| POST | /api/admin/install-demucs-model | admin |
| POST | /api/admin/remove-model | admin |
| POST | /api/admin/reload-model | admin |
| GET | /api/admin/jobs | admin |

## FAQ

**Vì sao job bị kẹt ở một mốc % mãi không tăng?**
Thường do container bị Railway restart giữa chừng vì hết RAM (OOM) khi xử lý file dài.
Từ bản cập nhật này, hệ thống tự giới hạn: Music Analyzer chỉ xử lý tối đa `AAS_MAX_ANALYSIS_SECONDS`
giây đầu (mặc định 240s) và downsample về `AAS_ANALYSIS_SAMPLE_RATE` (mặc định 22050Hz); Vocal
Remover chỉ xử lý tối đa `AAS_MAX_SEPARATION_SECONDS` giây đầu (mặc định 360s). Job Queue cũng
chỉ chạy 1 job cùng lúc (`AAS_JOB_QUEUE_WORKERS=1`) để không cộng dồn RAM. Có thể chỉnh các giá trị
này qua biến môi trường nếu server có nhiều RAM hơn.

**Vì sao "Tách vocal" báo lỗi "Model chưa được cài đặt"?**
Vocal Remover đã có pipeline inference thật (Demucs), nhưng cần admin cài model trước qua
`POST /api/admin/install-demucs-model` (xem mục "Thêm model mới" bên trên) — hệ thống không
tự cài sẵn model nào để tránh tải weights không cần thiết lúc khởi động.

**Vì sao dùng flat-file JSON thay vì database?**
Phù hợp quy mô self-host single-node, dễ backup, không cần cài thêm DB server. Có thể thay bằng
PostgreSQL/SQLite sau này mà không đổi API contract, vì mọi truy cập dữ liệu đều đi qua
`backend/core/*.py`.

**Tên file/thư mục có nên chứa ký tự đặc biệt như `#` không?**
Không — sẽ vỡ URL khi deploy qua Apache/cPanel. `storage.py` đã tự động làm sạch tên file khi upload.
