# Audio AI Suite

Ứng dụng web xử lý âm thanh bằng AI mã nguồn mở, chạy hoàn toàn trên server (self-host, không dùng API trả phí).

> **Trạng thái hiện tại: Giai đoạn 1/3.** Đã hoàn thiện: kiến trúc, auth (JWT + phân quyền),
> job queue, model registry, storage, Music Analyzer (BPM/Key/Chord bằng librosa — xử lý thật),
> frontend cơ bản (login, upload, dashboard admin, polling job). **Chưa hoàn thiện:** pipeline
> inference thật cho Vocal Remover (MDX-Net/VS-HsBtl) — route đã có sẵn khung, sẽ cắm model
> PyTorch thật ở Giai đoạn 2. Frontend sẽ được hoàn thiện thêm về UI/UX ở Giai đoạn 3.

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

## Thêm model mới (Model Manager)

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
| POST | /api/analyze | user |
| POST | /api/separate | user |
| GET | /api/job/{id} | user (chủ job) / admin |
| GET | /api/download/{id} | user (chủ job) / admin |
| GET | /api/admin/dashboard | admin |
| GET | /api/admin/models | admin |
| POST | /api/admin/install-model | admin |
| POST | /api/admin/remove-model | admin |
| POST | /api/admin/reload-model | admin |
| GET | /api/admin/jobs | admin |

## FAQ

**Vì sao Vocal Remover trả lỗi 501/NotImplementedError?**
Route đã hoàn chỉnh về kiến trúc (queue, registry, phân quyền) nhưng pipeline inference PyTorch
thật cho MDX-Net/VS-HsBtl sẽ được bổ sung ở Giai đoạn 2, để tránh xuất "kết quả giả".

**Vì sao dùng flat-file JSON thay vì database?**
Phù hợp quy mô self-host single-node, dễ backup, không cần cài thêm DB server. Có thể thay bằng
PostgreSQL/SQLite sau này mà không đổi API contract, vì mọi truy cập dữ liệu đều đi qua
`backend/core/*.py`.

**Tên file/thư mục có nên chứa ký tự đặc biệt như `#` không?**
Không — sẽ vỡ URL khi deploy qua Apache/cPanel. `storage.py` đã tự động làm sạch tên file khi upload.
