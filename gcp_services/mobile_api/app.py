from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading
from flask import Flask, jsonify, request


def create_app(source=None):
    app = Flask(__name__)
    repository = source
    repository_lock = threading.Lock()

    @app.before_request
    def authenticate():
        if request.path == '/health':
            return None
        expected = os.getenv('ACCESS_TOKEN_SHA256', '')
        header = request.headers.get('Authorization','')
        token = header[7:] if header.startswith('Bearer ') else ''
        if not expected or len(token) < 24 or len(token) > 512 or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),expected):
            return jsonify(error='unauthorized',message='Código de acceso incorrecto.'),401

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def get_repository():
        nonlocal repository
        if repository is None:
            with repository_lock:
                if repository is None:
                    from sources import PublishedSources
                    repository = PublishedSources()
        return repository

    @app.get('/health')
    def health():
        return jsonify(status='ok',service='growth-mobile',version=1)

    @app.get('/v1/dashboard')
    def dashboard():
        try:
            return jsonify(get_repository().snapshot())
        except Exception:
            logging.exception('Dashboard unavailable')
            return jsonify(error='unavailable',message='No se pudieron leer los datos publicados. Inténtalo de nuevo.'),503

    @app.get('/v1/reports/<symbol>')
    def report(symbol):
        if not re.fullmatch(r'[A-Z0-9.-]{1,12}',symbol):
            return jsonify(error='not_found'),404
        try:
            payload = get_repository().report(symbol)
            if payload is None:
                return jsonify(error='not_found',message='Informe no disponible.'),404
            return jsonify(payload)
        except Exception:
            logging.exception('Report unavailable')
            return jsonify(error='unavailable',message='No se pudo cargar el informe.'),503

    return app


app = create_app()
