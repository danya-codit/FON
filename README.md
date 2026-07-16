# FON

Локальное веб-приложение для удаления фона с фотографий. Интерфейс написан на Next.js и TypeScript, API — на FastAPI, сегментация выполняется моделью [BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet).

После однократного скачивания весов обработка работает полностью локально: backend загружает модель только из `models/BiRefNet` с параметром `local_files_only=True`. Фотографии не сохраняются на диск и не отправляются во внешние сервисы.

## Возможности

- JPG, PNG и WebP;
- выбор файла и drag-and-drop;
- проверка формата, размера файла и разрешения;
- предпросмотр исходника;
- удаление фона с помощью BiRefNet;
- прозрачная шахматная подложка результата;
- интерактивное сравнение «до/после»;
- скачивание результата в PNG;
- понятные состояния загрузки и ошибки;
- адаптивный интерфейс для компьютера и телефона.

## Структура

```text
FON/
├── backend/
│   ├── app/                    # FastAPI и сервис BiRefNet
│   ├── scripts/download_model.py
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── app/                    # Next.js App Router
│   ├── components/
│   ├── public/
│   ├── Dockerfile
│   └── .dockerignore
├── models/                      # Локальные веса BiRefNet, не попадают в Git
├── compose.yaml
├── .env.example
├── .gitignore
└── README.md
```

`models/` — единственное место для весов. Docker не включает их в образ: при запуске Compose папка монтируется в backend как read-only volume.

## Запуск через Docker

Docker — дополнительный способ запуска. Обычный запуск через Python и pnpm ниже продолжает работать.

### Требования

- Docker Desktop для Windows с Linux containers и WSL 2 backend;
- минимум 8 ГБ RAM для Docker Desktop, рекомендуется 16 ГБ на компьютере;
- около 8 ГБ свободного места для образов, зависимостей и модели;
- доступ в интернет нужен для первой сборки образов и первого скачивания модели. В runtime контейнеры работают без обращения к Hugging Face.

### 1. Открыть проект и проверить Docker

```powershell
cd C:\Users\Danya\Desktop\FON
docker version
docker compose version
```

### 2. Один раз скачать модель на хост

Команда использует уже настроенное Python-окружение backend и кладёт веса только в `C:\Users\Danya\Desktop\FON\models\BiRefNet`:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\download_model.py
Test-Path .\models\BiRefNet\model.safetensors
```

Если второй вывод — `True`, веса готовы. Они не попадают в Git и не копируются в Docker image.

### 3. Создать локальную конфигурацию

```powershell
Copy-Item .env.example .env
```

При необходимости измените порты, лимиты или CORS origins только в `.env`. Файл исключён из Git.

### 4. Собрать и запустить

```powershell
docker compose build
docker compose up -d
docker compose ps
```

Откройте frontend: [http://localhost:3000](http://localhost:3000).

Проверки backend:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Start-Process http://localhost:8000/docs
```

Frontend получает адрес API только из build-time переменной `NEXT_PUBLIC_API_URL`. Для Docker Compose по умолчанию это `http://localhost:8000`, потому что именно по этому адресу браузер пользователя видит опубликованный порт backend. В production-коде адрес не зашит: для другого хоста или порта измените `.env` и пересоберите frontend.

### Логи, остановка и пересборка

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
docker compose up --build -d
```

`docker compose down` удаляет контейнеры и сеть, но не трогает `models/` — это bind mount на вашем диске.

### Проверка без интернета

После первой сборки и скачивания весов отключите интернет и выполните:

```powershell
docker compose up -d --no-build
Invoke-RestMethod http://localhost:8000/api/health
```

Compose устанавливает `HF_HUB_OFFLINE=1` и `TRANSFORMERS_OFFLINE=1`, а приложение использует `local_files_only=True`. Поэтому при отсутствии модели backend вернёт понятный HTTP 503 с командой скачивания, а не начнёт загрузку с Hugging Face.

### Очистка Docker-кэша без удаления модели

```powershell
docker builder prune -f
docker image prune -f
```

Не используйте `Remove-Item .\models` и не добавляйте `models/` в Docker volumes cleanup: это единственная локальная копия весов.

### Ожидаемые размеры образов

- `fon-frontend:local`: обычно менее 250 МБ благодаря standalone-сборке;
- `fon-backend:local`: ориентировочно 1–2 ГБ; используется CPU-версия PyTorch без CUDA-библиотек.

После сборки точные размеры покажет команда:

```powershell
docker images fon-frontend:local fon-backend:local
```

### Частые проблемы Docker Desktop и WSL

**Docker Engine не запускается.** Откройте Docker Desktop и дождитесь статуса **Engine running**. Затем выполните:

```powershell
docker desktop status
wsl --status
wsl --update
wsl --shutdown
```

После `wsl --shutdown` перезапустите Docker Desktop. В настройках Docker Desktop должен быть включён **Use the WSL 2 based engine**; также убедитесь, что виртуализация включена в BIOS/UEFI.

**Backend пишет, что модель не найдена.** Проверьте путь `C:\Users\Danya\Desktop\FON\models\BiRefNet\model.safetensors` и снова выполните команду скачивания из шага 2.

**Не хватает памяти.** Увеличьте память в Docker Desktop → Settings → Resources. Значение `BACKEND_MEMORY_LIMIT` в `.env` можно повысить, если Docker сообщает об out-of-memory.

## Production backend для Yandex Serverless Containers

Production-образ создаётся отдельно от локального Compose. Он включает локальную папку
`models/BiRefNet` в `/app/models/BiRefNet`, включает `HF_HUB_OFFLINE=1` и
`TRANSFORMERS_OFFLINE=1` и не требует bind-volume с моделью. В Git веса по-прежнему не
попадают: они исключены через `.gitignore`, но разрешены только в build context production-образа.

### Собрать и проверить production image локально

Из корня проекта:

```powershell
.\scripts\build-production-backend.ps1
.\scripts\run-production-backend-local.ps1 -Port 8080
```

Во втором окне PowerShell:

```powershell
.\scripts\test-production-backend.ps1 -Port 8080
```

Скрипт запуска передаёт `PORT=8080`, но volume не подключает. Если `PORT` не задан,
образ слушает `8000`. Production Dockerfile использует один worker и healthcheck.

Для сборки frontend под публичный URL backend передайте build args:

```powershell
docker build -f frontend\Dockerfile -t fon-frontend:production frontend `
  --build-arg NEXT_PUBLIC_API_URL=https://<public-backend-url> `
  --build-arg NEXT_PUBLIC_UPLOAD_MODE=storage `
  --build-arg NEXT_PUBLIC_MAX_FILE_SIZE_MB=15
```

`NEXT_PUBLIC_API_URL` — browser-visible URL API; в production он не должен быть
`localhost`. В локальном Compose по умолчанию используются `http://localhost:8000` и
`NEXT_PUBLIC_UPLOAD_MODE=direct`, поэтому привычный локальный сценарий не меняется.

### Поток Object Storage

Для Serverless Containers прямой multipart endpoint остаётся локальным режимом. Production
frontend при `NEXT_PUBLIC_UPLOAD_MODE=storage` использует следующий поток:

1. `POST /api/uploads/presign` выдаёт одноразовую signed URL и ключ `uploads/...`.
2. Браузер отправляет исходный файл напрямую по этой ссылке.
3. `POST /api/remove-background/jobs` получает ключ, загружает файл из закрытого bucket,
   обрабатывает его и сохраняет PNG в `results/...`.
4. API возвращает signed URL результата, а `GET /api/remove-background/jobs/{id}` позволяет
   посмотреть состояние синхронного задания в текущем процессе.

Для разработки `STORAGE_BACKEND=mock` создаёт файловый mock в `backend/.storage/` и добавляет
временные URL через API. Для Yandex Object Storage установите `STORAGE_BACKEND=s3` и задайте
следующие переменные только в защищённых настройках revision, а не в Git:

| Переменная | Назначение |
| --- | --- |
| `S3_ENDPOINT` | `https://storage.yandexcloud.net` |
| `S3_BUCKET` | Закрытый bucket для `uploads/` и `results/` |
| `S3_REGION` | Обычно `ru-central1` |
| `S3_ACCESS_KEY_ID` | Статический ключ сервисного аккаунта |
| `S3_SECRET_ACCESS_KEY` | Секрет статического ключа |
| `PRESIGN_EXPIRES_SECONDS` | Время действия signed URLs, по умолчанию 900 |

На bucket вручную нужно будет настроить CORS для публичного домена frontend (методы `PUT` и
`GET`) и lifecycle policy, удаляющую `uploads/` и `results/` через заданный срок. В проекте не
создаются bucket, ключи, lifecycle policy или иные платные ресурсы Yandex Cloud.

При создании revision Yandex Serverless Containers укажите production image из Yandex Container
Registry, `PORT` из runtime, достаточную память для CPU-инференса и service account с доступом
к Container Registry. Если вместо весов в image используется mount bucket, сервисному аккаунту
понадобится `storage.viewer`; для первого production запуска предпочтительнее образ с весами.

## Локальный запуск без Docker

## Системные требования

- Windows 10/11 x64;
- Python 3.10–3.12 (проверено на Python 3.12);
- Node.js 20.9 или новее;
- pnpm 11.7;
- от 8 ГБ RAM, рекомендуется 16 ГБ;
- несколько гигабайт свободного места для Python-пакетов и модели;
- интернет только для установки зависимостей и первого скачивания модели.

Видеокарта не обязательна. При наличии совместимой NVIDIA CUDA будет выбрана автоматически; без неё приложение работает на CPU, но обработка занимает больше времени.

## Установка на Windows через PowerShell

### 1. Клонировать репозиторий

```powershell
git clone https://github.com/danya-codit/FON.git
cd FON
```

### 2. Настроить backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если PowerShell запрещает активацию скрипта, один раз выполните в текущем окне:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Один раз скачать BiRefNet

Из папки `backend` и с активным Python-окружением:

```powershell
python scripts\download_model.py
```

Файлы попадут в `models/BiRefNet`. Папка исключена из Git. Повторно скачивать модель при каждом запуске не нужно. Для принудительного обновления есть команда:

```powershell
python scripts\download_model.py --force
```

### 4. Запустить backend

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health). Документация API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Оставьте это окно открытым.

### 5. Настроить и запустить frontend

Откройте второе окно PowerShell в корне проекта:

```powershell
cd frontend
npm install --global pnpm@11.7.0
pnpm install
pnpm dev
```

Откройте [http://127.0.0.1:3000](http://127.0.0.1:3000).

## Использование существующего Anaconda-окружения

Отдельный `venv` не обязателен. Если в Anaconda уже установлены Python и Torch, активируйте это окружение и установите недостающие зависимости. Совместимые пакеты pip оставит без изменений.

```powershell
conda activate YOUR_ENV_NAME
cd path\to\FON\backend
python --version
python -c "import torch; print(torch.__version__)"
python -m pip install -r requirements.txt
python scripts\download_model.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Python должен быть версии 3.10–3.12, а установленные `torch`, `torchvision` и остальные библиотеки — удовлетворять диапазонам из `backend/requirements.txt`. Если нужна определённая CUDA-сборка Torch, сначала установите её командой с официальной страницы [PyTorch Get Started](https://pytorch.org/get-started/locally/), затем выполните установку requirements.

## Настройка в PyCharm

### Python interpreter

1. Откройте корневую папку `FON` в PyCharm.
2. Перейдите в **Settings → Project → Python Interpreter**.
3. Выберите один вариант:
   - **Add Interpreter → Existing** и укажите `FON\backend\.venv\Scripts\python.exe`;
   - **Add Interpreter → Conda → Existing environment** и выберите `python.exe` вашего Anaconda-окружения.
4. Откройте встроенный Terminal, перейдите в `backend` и выполните `python -m pip install -r requirements.txt`.

### Конфигурация скачивания модели

Создайте **Run/Debug Configuration → Python**:

- **Name:** `Download BiRefNet`;
- **Script path:** `FON\backend\scripts\download_model.py`;
- **Working directory:** `FON\backend`;
- **Python interpreter:** выбранное `.venv` или Conda-окружение.

Запустите конфигурацию один раз.

### Конфигурация backend

Создайте **Run/Debug Configuration → Python**:

- **Name:** `FON Backend`;
- включите **Module name** и укажите `uvicorn`;
- **Parameters:** `app.main:app --reload --host 127.0.0.1 --port 8000`;
- **Working directory:** `FON\backend`;
- **Python interpreter:** выбранное окружение.

### Конфигурация frontend

1. В **Settings → Languages & Frameworks → Node.js** выберите установленный Node.js и pnpm.
2. Выполните `pnpm install` в папке `frontend`.
3. Создайте **Run/Debug Configuration → npm** (PyCharm понимает скрипты из `package.json`):
   - **package.json:** `FON\frontend\package.json`;
   - **Command:** `run`;
   - **Scripts:** `dev`.

Запустите `FON Backend`, затем frontend-конфигурацию.

## Настройки окружения

Backend читает следующие переменные:

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `BIREFNET_MODEL_DIR` | `models/BiRefNet` | Локальная папка модели |
| `BIREFNET_MODEL_ID` | `ZhengPeng7/BiRefNet` | Репозиторий для команды скачивания |
| `MAX_UPLOAD_SIZE_MB` | `15` | Максимальный размер файла |
| `MAX_IMAGE_PIXELS` | `40000000` | Защита от изображений чрезмерного разрешения |
| `ALLOWED_ORIGINS` | localhost и 127.0.0.1:3000 | Разрешённые CORS origins через запятую |
| `STORAGE_BACKEND` | `mock` | `mock` для разработки или `s3` для Yandex Object Storage |
| `STORAGE_MOCK_DIR` | `backend/.storage` | Локальная папка mock storage, исключена из Git |
| `S3_*` | пусто | S3-совместимые параметры production bucket, не коммитятся |
| `PRESIGN_EXPIRES_SECONDS` | `900` | Время действия signed URLs |

Frontend:

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | задаётся в `frontend/.env.local` | Browser-visible адрес FastAPI |
| `NEXT_PUBLIC_MAX_FILE_SIZE_MB` | `15` | Клиентская проверка размера |
| `NEXT_PUBLIC_UPLOAD_MODE` | `direct` | `direct` для local API или `storage` для production flow |

Примеры находятся в `backend/.env.example` и `frontend/.env.local.example`. При изменении лимита задайте одинаковое значение на frontend и backend. Секреты и локальные `.env` исключены из Git.

Для запуска backend с файлом `.env`:

```powershell
python -m uvicorn app.main:app --reload --env-file .env
```

## Полностью офлайн после установки

После выполнения `download_model.py` можно явно включить offline-режим библиотек и запустить API:

```powershell
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

FastAPI использует `local_files_only=True`, поэтому обработка не обращается к Hugging Face и без этих переменных. Они полезны как дополнительная проверка.

## Проверки

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest
```

Frontend:

```powershell
cd frontend
pnpm lint
pnpm typecheck
pnpm build
```

## API

- `GET /api/health` — состояние API и локальной модели;
- `GET /api/config` — публичные ограничения загрузки;
- `POST /api/remove-background` — multipart-поле `file`, ответ `image/png`.
- `POST /api/uploads/presign` — signed URL и ключ объекта для прямой загрузки;
- `POST /api/remove-background/jobs` — обработка объекта из storage и signed URL PNG;
- `GET /api/remove-background/jobs/{id}` — состояние синхронного задания в памяти процесса.

Если модель не скачана, endpoint обработки возвращает HTTP 503 с командой установки. Неверный формат возвращает 415, повреждённое или слишком большое по разрешению изображение — 422, файл больше лимита — 413.

## Частые проблемы

**Frontend пишет, что нет соединения с API.** Убедитесь, что uvicorn работает на `127.0.0.1:8000`, а `NEXT_PUBLIC_API_URL` в `frontend/.env.local` указывает на тот же адрес. После изменения пересоберите или перезапустите Next.js.

**API сообщает, что BiRefNet не найден.** Активируйте то же Python-окружение, из которого запускается uvicorn, перейдите в `backend` и выполните `python scripts\download_model.py`.

**Обработка на CPU медленная.** Это ожидаемо для BiRefNet с входом 1024×1024. Оставьте вкладку открытой и дождитесь ответа. Для NVIDIA установите совместимую CUDA-сборку Torch.

**Нужно перенести модель на другой диск.** Установите `BIREFNET_MODEL_DIR` перед скачиванием и перед каждым запуском backend; оба процесса должны видеть один и тот же путь.
