from __future__ import annotations

import hashlib
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

import requests
import streamlit as st


class CloudinaryConfigError(RuntimeError):
    """Indica que as credenciais do Cloudinary estão ausentes ou incompletas."""


@dataclass(frozen=True)
class UploadedImage:
    url: str
    public_id: str


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


def _read_config(secrets: Mapping[str, Any]) -> dict[str, str]:
    if "cloudinary" not in secrets:
        raise CloudinaryConfigError(
            "Adicione a seção [cloudinary] nas secrets do Streamlit."
        )
    raw = _to_dict(secrets["cloudinary"])
    required = ("cloud_name", "api_key", "api_secret")
    missing = [name for name in required if not str(raw.get(name, "")).strip()]
    if missing:
        raise CloudinaryConfigError(
            "Configuração incompleta do Cloudinary: " + ", ".join(missing)
        )
    return {
        "cloud_name": str(raw["cloud_name"]).strip(),
        "api_key": str(raw["api_key"]).strip(),
        "api_secret": str(raw["api_secret"]).strip(),
        "folder": str(
            raw.get("folder", "confeitaria julia/receitas")
        ).strip(),
    }


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def upload_recipe_image(
    uploaded_file: Any,
    recipe_code: str,
    recipe_name: str,
) -> UploadedImage:
    """Envia uma imagem ao Cloudinary e devolve sua URL HTTPS permanente."""
    config = _read_config(st.secrets)
    timestamp = int(time.time())
    unique_suffix = uuid.uuid4().hex[:10]
    public_id = (
        f"receita-{recipe_code}-{_slug(recipe_name) or 'sem-nome'}-"
        f"{timestamp}-{unique_suffix}"
    )
    signed_parameters = {
        "asset_folder": config["folder"],
        "overwrite": "true",
        "public_id": public_id,
        "timestamp": str(timestamp),
    }
    signature_source = "&".join(
        f"{key}={value}" for key, value in sorted(signed_parameters.items())
    )
    signature = hashlib.sha1(
        f"{signature_source}{config['api_secret']}".encode("utf-8")
    ).hexdigest()

    uploaded_file.seek(0)
    response = requests.post(
        (
            "https://api.cloudinary.com/v1_1/"
            f"{config['cloud_name']}/image/upload"
        ),
        data={
            **signed_parameters,
            "api_key": config["api_key"],
            "signature": signature,
        },
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type,
            )
        },
        timeout=60,
    )
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(
            "O Cloudinary retornou uma resposta inválida."
        ) from error
    if not response.ok:
        message = payload.get("error", {}).get("message", response.reason)
        raise RuntimeError(f"Falha no envio da foto ao Cloudinary: {message}")
    secure_url = str(payload.get("secure_url", "")).strip()
    if not secure_url:
        raise RuntimeError("O Cloudinary não retornou a URL segura da imagem.")
    return UploadedImage(url=secure_url, public_id=public_id)


def _public_id_from_url(image_url: str) -> str | None:
    """Extrai apenas IDs gerados por este aplicativo."""
    parsed = urlparse(image_url)
    if parsed.hostname != "res.cloudinary.com" or "/upload/" not in parsed.path:
        return None
    tail = unquote(parsed.path.split("/upload/", 1)[1])
    parts = [part for part in tail.split("/") if part]
    if parts and re.fullmatch(r"v\d+", parts[0]):
        parts = parts[1:]
    if not parts:
        return None
    parts[-1] = parts[-1].rsplit(".", 1)[0]
    public_id = "/".join(parts)
    return public_id if public_id.startswith("receita-") else None


def delete_recipe_image(
    public_id_or_url: str,
    *,
    is_url: bool = False,
) -> bool:
    """Remove uma imagem criada pelo app; URLs externas são ignoradas."""
    config = _read_config(st.secrets)
    public_id = (
        _public_id_from_url(public_id_or_url)
        if is_url
        else public_id_or_url.strip()
    )
    if not public_id or not public_id.startswith("receita-"):
        return False
    timestamp = int(time.time())
    signed_parameters = {
        "invalidate": "true",
        "public_id": public_id,
        "timestamp": str(timestamp),
    }
    signature_source = "&".join(
        f"{key}={value}" for key, value in sorted(signed_parameters.items())
    )
    signature = hashlib.sha1(
        f"{signature_source}{config['api_secret']}".encode("utf-8")
    ).hexdigest()
    response = requests.post(
        (
            "https://api.cloudinary.com/v1_1/"
            f"{config['cloud_name']}/image/destroy"
        ),
        data={
            **signed_parameters,
            "api_key": config["api_key"],
            "signature": signature,
        },
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(
            "O Cloudinary retornou uma resposta inválida ao excluir a foto."
        ) from error
    if not response.ok:
        message = payload.get("error", {}).get("message", response.reason)
        raise RuntimeError(f"Falha ao excluir a foto antiga: {message}")
    return payload.get("result") in {"ok", "not found"}
