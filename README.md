# FON

Локальное веб-приложение для удаления фона с фотографий. Интерфейс написан на Next.js и TypeScript, API — на FastAPI, сегментация выполняется моделью [BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet).

После однократного скачивания весов обработка работает полностью локально: backend загружает модель только из `backend/models/BiRefNet` с параметром `local_files_only=True`. Фотографии не сохраняются на диск и не отправляются во внешние сервисы.

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
│   └── requirements-dev.txt
├── frontend/
│   ├── app/                    # Next.js App Router
│   ├── components/
│   └── public/
├── .gitignore
└── README.md
```

Docker и облачное развёртывание намеренно не добавлены: текущая версия предназначена для локального запуска.

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

Файлы попадут в `backend/models/BiRefNet`. Папка исключена из Git. Повторно скачивать модель при каждом запуске не нужно. Для принудительного обновления есть команда:

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
| `BIREFNET_MODEL_DIR` | `backend/models/BiRefNet` | Локальная папка модели |
| `BIREFNET_MODEL_ID` | `ZhengPeng7/BiRefNet` | Репозиторий для команды скачивания |
| `MAX_UPLOAD_SIZE_MB` | `15` | Максимальный размер файла |
| `MAX_IMAGE_PIXELS` | `40000000` | Защита от изображений чрезмерного разрешения |
| `ALLOWED_ORIGINS` | localhost и 127.0.0.1:3000 | Разрешённые CORS origins через запятую |

Frontend:

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Адрес FastAPI |
| `NEXT_PUBLIC_MAX_FILE_SIZE_MB` | `15` | Клиентская проверка размера |

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

Если модель не скачана, endpoint обработки возвращает HTTP 503 с командой установки. Неверный формат возвращает 415, повреждённое или слишком большое по разрешению изображение — 422, файл больше лимита — 413.

## Частые проблемы

**Frontend пишет, что нет соединения с API.** Убедитесь, что uvicorn работает на `127.0.0.1:8000`, а `NEXT_PUBLIC_API_URL` указывает на тот же адрес.

**API сообщает, что BiRefNet не найден.** Активируйте то же Python-окружение, из которого запускается uvicorn, перейдите в `backend` и выполните `python scripts\download_model.py`.

**Обработка на CPU медленная.** Это ожидаемо для BiRefNet с входом 1024×1024. Оставьте вкладку открытой и дождитесь ответа. Для NVIDIA установите совместимую CUDA-сборку Torch.

**Нужно перенести модель на другой диск.** Установите `BIREFNET_MODEL_DIR` перед скачиванием и перед каждым запуском backend; оба процесса должны видеть один и тот же путь.
