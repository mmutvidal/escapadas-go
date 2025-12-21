https://developers.facebook.com/tools/explorer
https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id=1371073527917893&client_secret=fe24f2ff095d83f9a9aed6513edfa818&fb_exchange_token=EAATeZBZB6XrUUBQKzrGOvacZABAJJ0tG9z9zm2BhmEEg7l038U2QcbZAnGGRhbSDDHNhGDNXjjh5DbWxgeiLm8MsQDxsnDY4nSbnMkGJCDBann1B3ZC3jzRuy17p1ZAbqOCIpGJsZBRKNOWZAytX1UuaNF86XKRRWdOoWifRWFQPom2Sa1J7134pONdPZCaqwEYhBT7mJeKZAdRZAhLpknyH0cmtLAcoRRlOS8lRCYrSmIym2PEL9ZBWAEZBU3qRqHVtSaZAX50zIeZANhRXlnOmzMfUxiyXknN

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


