from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


class GoogleSheetsConfigError(RuntimeError):
    """Indica que a configuração do Google Sheets está ausente ou incompleta."""


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


@dataclass(frozen=True)
class GoogleSheetsClient:
    spreadsheet_id: str
    _client: gspread.Client

    @classmethod
    def from_streamlit_secrets(cls) -> "GoogleSheetsClient":
        try:
            credentials_data = _read_credentials(st.secrets)
            spreadsheet_id = _read_spreadsheet_id(st.secrets)
        except GoogleSheetsConfigError:
            raise
        except Exception as error:
            # Algumas versões do Streamlit só levantam SecretNotFoundError quando
            # st.secrets é efetivamente acessado. Convertemos para a exceção da
            # aplicação para permitir que a interface abra sem credenciais locais.
            if error.__class__.__name__ == "StreamlitSecretNotFoundError":
                raise GoogleSheetsConfigError(
                    "O arquivo .streamlit/secrets.toml ainda não foi criado."
                ) from error
            raise
        credentials = Credentials.from_service_account_info(
            credentials_data,
            scopes=SCOPES,
        )
        return cls(
            spreadsheet_id=spreadsheet_id,
            _client=gspread.authorize(credentials),
        )

    def spreadsheet(self) -> gspread.Spreadsheet:
        return self._client.open_by_key(self.spreadsheet_id)

    def worksheet(self, name: str) -> gspread.Worksheet:
        return self.spreadsheet().worksheet(name)

    def get_records(self, worksheet_name: str) -> list[dict[str, Any]]:
        return self.worksheet(worksheet_name).get_all_records()

    def append_row(self, worksheet_name: str, values: list[Any]) -> None:
        self.worksheet(worksheet_name).append_row(
            values,
            value_input_option="USER_ENTERED",
        )

    def append_rows(self, worksheet_name: str, values: list[list[Any]]) -> None:
        self.worksheet(worksheet_name).append_rows(
            values,
            value_input_option="USER_ENTERED",
        )

    def next_integer_code(self, worksheet_name: str, column: int = 1) -> int:
        values = self.worksheet(worksheet_name).col_values(column)[1:]
        codes: list[int] = []
        for value in values:
            try:
                codes.append(int(float(str(value).replace(",", "."))))
            except (TypeError, ValueError):
                continue
        return max(codes, default=0) + 1


def _read_credentials(secrets: Mapping[str, Any]) -> dict[str, Any]:
    # Aceita os dois nomes mais usados nos projetos Streamlit.
    for section_name in ("gcp_service_account", "google_credentials"):
        if section_name in secrets:
            data = _to_dict(secrets[section_name])
            if "private_key" in data:
                data["private_key"] = data["private_key"].replace("\\n", "\n")
            return data
    raise GoogleSheetsConfigError(
        "Credencial não encontrada em [gcp_service_account] ou [google_credentials]."
    )


def _read_spreadsheet_id(secrets: Mapping[str, Any]) -> str:
    if "spreadsheet_id" in secrets:
        return str(secrets["spreadsheet_id"])
    if "google_sheets" in secrets and "spreadsheet_id" in secrets["google_sheets"]:
        return str(secrets["google_sheets"]["spreadsheet_id"])
    raise GoogleSheetsConfigError("O spreadsheet_id não foi configurado.")
