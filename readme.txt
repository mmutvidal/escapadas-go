Para lanzar los 3 de abajo

cd "C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca"
python run_services.py


(Para escuchar respuesta de Telegram:

cd "C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca"
python -m review.telegram_review


Para tener el video disponible a través de una URL:

cd "C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca"
python -m http.server 8000

ngrok http 8000 )


Arquitectura:

escapadas_mallorca_bot/
├── .env
├── main.py                        # flujo diario principal
│
├── config/
│   └── settings.py                # claves, tokens, constantes
│
├── flights/                       # APIs de vuelos
│   ├── base.py                    # interfaz común
│   ├── api_ryanair.py
│   ├── api_vueling.py
│   ├── api_my_custom.py
│   └── aggregator.py              # elige el mejor vuelo entre API(s)
│
├── places/                        # Google Places (restaurantes, etc.)
│   ├── api_google_places.py
│   └── recommender.py             # busca sitios relevantes
│
├── content/
│   ├── caption_builder.py         # OpenAI para generar JSON del caption
│   └── prompts.py                 # plantilla del prompt
│
├── media/
│   ├── images/
│   ├── videos/
│   ├── image_picker.py            # elige imagen según destino
│   └── video_generator.py         # moviepy: zoom + texto → MP4
│
├── storage/
│   └── uploader.py               # sube vídeo y genera URL pública
│
├── instagram/
│   ├── ig_client.py              # /media, polling, /media_publish
│   └── publish.py                # wrapper para publicar más fácil
│
└── review/                       # aprobación diaria
│   ├── telegram_review.py
│   └── state.py                  # guarda vuelo pendiente de decisión
│
└── review_jobs/                  # guarda los IDs de las publicaciones en Telegram para que 


