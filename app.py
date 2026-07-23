import streamlit as st
from threading import Lock

from services.cloudinary_images import delete_recipe_image, upload_recipe_image
from services.google_sheets import GoogleSheetsClient, GoogleSheetsConfigError
from ui.layout import configure_page, render_page_header, render_sidebar


configure_page()

MATERIALS_WORKSHEET = "BANCO DE DADOS "
RECIPES_WORKSHEET = "RECEITAS ATUALIZADO"
MATERIAL_WRITE_LOCK = Lock()
RECIPE_WRITE_LOCK = Lock()


def parse_brazilian_number(value: str) -> float | None:
    """Converte entradas como 1.234,56 ou 1234.56 para número."""
    normalized = value.strip().replace("R$", "").replace(" ", "")
    if not normalized:
        return None
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def load_registered_brands() -> list[str]:
    sheets = GoogleSheetsClient.from_streamlit_secrets()
    values = sheets.worksheet(MATERIALS_WORKSHEET).col_values(3)[1:]
    unique_brands = {value.strip() for value in values if value.strip()}
    return sorted(unique_brands, key=str.casefold)


@st.cache_data(ttl=300, show_spinner=False)
def load_materials() -> list[dict[str, object]]:
    sheets = GoogleSheetsClient.from_streamlit_secrets()
    rows = sheets.worksheet(MATERIALS_WORKSHEET).get_all_values()[1:]
    materials: list[dict[str, object]] = []
    for row in rows:
        if len(row) < 7:
            continue
        cost = parse_brazilian_number(row[6])
        if not row[0].strip() or not row[1].strip():
            continue
        label = f"{row[1].strip()} — {row[2].strip()} (cód. {row[0].strip()})"
        materials.append(
            {
                "code": row[0].strip(),
                "name": row[1].strip(),
                "brand": row[2].strip(),
                "purchase_quantity": parse_brazilian_number(row[3]),
                "unit": normalize_unit(row[4]),
                "price": parse_brazilian_number(row[5]),
                "unit_cost": cost,
                "label": label,
            }
        )
    return sorted(materials, key=lambda item: str(item["label"]).casefold())


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def normalize_unit(value: str) -> str:
    normalized = value.strip().casefold()
    # Registros antigos podem ter sido gravados com estas variações.
    if normalized in {"un", "um", "unidade", "unidae"}:
        return "UN"
    return normalized


UNIT_DIMENSIONS = {
    "g": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "ml": ("volume", 1.0),
    "l": ("volume", 1000.0),
    "UN": ("count", 1.0),
}


def convert_quantity_between_units(
    quantity: float,
    old_unit: str,
    new_unit: str,
) -> float:
    """Converte uma quantidade entre unidades compatíveis."""
    normalized_old = normalize_unit(old_unit)
    normalized_new = normalize_unit(new_unit)
    old_dimension, old_factor = UNIT_DIMENSIONS[normalized_old]
    new_dimension, new_factor = UNIT_DIMENSIONS[normalized_new]
    if old_dimension != new_dimension:
        raise ValueError(
            f"Não é possível converter automaticamente de {normalized_old} "
            f"para {normalized_new}."
        )
    return quantity * old_factor / new_factor


@st.cache_data(ttl=120, show_spinner=False)
def load_existing_recipes() -> list[dict[str, object]]:
    sheets = GoogleSheetsClient.from_streamlit_secrets()
    rows = sheets.worksheet(RECIPES_WORKSHEET).get_all_values()[1:]
    recipes_by_code: dict[str, dict[str, object]] = {}
    for raw_row in rows:
        row = raw_row + [""] * (9 - len(raw_row))
        code = row[0].strip()
        if not code:
            continue
        recipe = recipes_by_code.setdefault(
            code,
            {
                "code": code,
                "name": row[1].strip(),
                "profit": row[7].strip(),
                "photo": "",
                "items": [],
            },
        )
        if row[8].strip() and not recipe["photo"]:
            recipe["photo"] = row[8].strip()
        recipe["items"].append(
            {
                "material_code": row[2].strip(),
                "material_name": row[3].strip(),
                "quantity": row[4].strip(),
                "unit": normalize_unit(row[5]),
                "cost": row[6].strip(),
            }
        )
    return sorted(
        recipes_by_code.values(),
        key=lambda recipe: str(recipe["name"]).casefold(),
    )


def clear_app_data_cache() -> None:
    """Invalida todos os dados lidos da planilha após uma gravação."""
    st.cache_data.clear()


def material_already_exists(
    sheets: GoogleSheetsClient,
    ingredient: str,
    brand: str,
    quantity: float,
    unit: str,
    price: float,
    excluded_code: str | None = None,
) -> bool:
    rows = sheets.worksheet(MATERIALS_WORKSHEET).get_all_values()[1:]
    for row in rows:
        if len(row) < 6:
            continue
        if excluded_code and row[0].strip() == excluded_code:
            continue
        saved_quantity = parse_brazilian_number(row[3])
        saved_price = parse_brazilian_number(row[5])
        if saved_quantity is None or saved_price is None:
            continue
        same_material = (
            normalize_text(row[1]) == normalize_text(ingredient)
            and normalize_text(row[2]) == normalize_text(brand)
            and abs(saved_quantity - quantity) < 1e-9
            and normalize_unit(row[4]) == normalize_unit(unit)
            and abs(saved_price - price) < 1e-9
        )
        if same_material:
            return True
    return False


def render_connection_status() -> None:
    try:
        sheets = GoogleSheetsClient.from_streamlit_secrets()
    except GoogleSheetsConfigError:
        st.info(
            "A integração com o Google Sheets está pronta. "
            "Adicione a credencial em `.streamlit/secrets.toml` para ativá-la."
        )
        return
    except Exception as error:
        st.warning(
            "O aplicativo abriu, mas não foi possível validar a conexão com "
            f"o Google Sheets ({error.__class__.__name__}). Confira as secrets."
        )
        return

    st.success(f"Google Sheets configurado: `{sheets.spreadsheet_id}`")


def render_home() -> None:
    render_page_header(
        "Caju — Doces em família",
        "Gestão de receitas, ingredientes e produtos.",
    )
    left, right = st.columns([2, 1])
    with left:
        st.markdown(
            """
            <div class="caju-card">
                <h3>Cadastro de ingredientes</h3>
                <p style="margin-bottom:0">
                    Cadastre ingredientes e calcule automaticamente o custo por unidade.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        render_connection_status()


def render_new_ingredient_form() -> None:
    try:
        registered_brands = load_registered_brands()
    except Exception:
        registered_brands = []

    with st.container(border=False, key="material_form_panel"):
        st.markdown(
            '<p class="form-section-title">Identificação do ingrediente</p>',
            unsafe_allow_html=True,
        )
        ingredient_column, brand_column = st.columns(2)
        with ingredient_column:
            ingredient = st.text_input(
                "Ingrediente *",
                placeholder="Ex.: Leite condensado",
                key="new_ingredient_name",
            )
        with brand_column:
            brand = st.selectbox(
                "Marca *",
                options=registered_brands,
                index=None,
                placeholder="Selecione ou digite uma nova marca",
                accept_new_options=True,
                key="new_ingredient_brand",
            )

        st.markdown(
            '<p class="form-section-title">Embalagem e custo</p>',
            unsafe_allow_html=True,
        )
        quantity_column, unit_column, price_column = st.columns([1, 0.8, 1])
        with quantity_column:
            quantity_text = st.text_input(
                "Quantidade *",
                placeholder="Ex.: 395",
                key="new_ingredient_quantity",
            )
        with unit_column:
            unit = st.selectbox(
                "Unidade *",
                options=("g", "kg", "ml", "l", "UN"),
                index=0,
                key="new_ingredient_unit",
            )
        with price_column:
            price_text = st.text_input(
                "Valor pago (R$) *",
                placeholder="Ex.: 6,35",
                key="new_ingredient_price",
            )

        quantity = parse_brazilian_number(quantity_text)
        price = parse_brazilian_number(price_text)
        unit_cost = (
            price / quantity
            if price is not None and quantity is not None and quantity > 0
            else 0.0
        )
        formatted_cost = f"R$ {unit_cost:,.6f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.markdown(
            f"""
            <div class="cost-summary">
                <div>
                    <p class="cost-summary-label">Custo por unidade de medida</p>
                    <small>Valor calculado automaticamente</small>
                </div>
                <p class="cost-summary-value">{formatted_cost} / {unit}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        submitted = st.button(
            "Cadastrar ingrediente",
            use_container_width=True,
            key="new_submit_ingredient",
            disabled=st.session_state.get("new_ingredient_save_in_progress", False),
        )

    if not submitted:
        return

    errors = []
    if not ingredient.strip():
        errors.append("Informe o ingrediente.")
    if not brand or not brand.strip():
        errors.append("Informe a marca.")
    if quantity is None:
        errors.append("Informe uma quantidade válida.")
    elif quantity <= 0:
        errors.append("A quantidade deve ser maior que zero.")
    if price is None:
        errors.append("Informe um valor pago válido.")
    elif price <= 0:
        errors.append("O valor pago deve ser maior que zero.")

    if errors:
        st.error(" ".join(errors))
        return

    if st.session_state.get("new_ingredient_save_in_progress", False):
        st.warning("Cadastro em andamento. Aguarde a conclusão.")
        return

    st.session_state.new_ingredient_save_in_progress = True
    try:
        # A trava mantém a consulta de duplicidade e a gravação como uma única
        # operação dentro deste servidor, inclusive entre sessões simultâneas.
        with MATERIAL_WRITE_LOCK:
            sheets = GoogleSheetsClient.from_streamlit_secrets()
            if material_already_exists(
                sheets,
                ingredient=ingredient,
                brand=brand,
                quantity=quantity,
                unit=unit,
                price=price,
            ):
                st.warning(
                    "Este ingrediente já está cadastrado com a mesma marca, "
                    "quantidade, unidade e valor pago."
                )
                return
            code = sheets.next_integer_code(MATERIALS_WORKSHEET)
            sheets.append_row(
                MATERIALS_WORKSHEET,
                [
                    code,
                    ingredient.strip(),
                    brand.strip(),
                    quantity,
                    unit,
                    price,
                    unit_cost,
                ],
            )
        clear_app_data_cache()
    except Exception as error:
        st.error(f"Não foi possível salvar o cadastro: {error}")
        return
    finally:
        st.session_state.new_ingredient_save_in_progress = False

    st.success(f"Ingrediente cadastrado com sucesso. Código: {code}.")


def build_ingredient_recipe_updates(
    sheets: GoogleSheetsClient,
    ingredient_code: str,
    ingredient_name: str,
    old_unit: str,
    new_unit: str,
    unit_cost: float,
) -> list[dict[str, object]]:
    """Prepara atualizações das receitas, convertendo quantidades se necessário."""
    worksheet = sheets.worksheet(RECIPES_WORKSHEET)
    rows = worksheet.get_all_values()[1:]
    updates: list[dict[str, object]] = []
    for sheet_row, raw_row in enumerate(rows, start=2):
        row = raw_row + [""] * (9 - len(raw_row))
        if row[2].strip() != ingredient_code:
            continue
        used_quantity = parse_brazilian_number(row[4])
        converted_quantity: float | str = ""
        if used_quantity is not None:
            converted_quantity = convert_quantity_between_units(
                used_quantity,
                old_unit,
                new_unit,
            )
        item_cost: float | str = (
            float(converted_quantity) * unit_cost
            if converted_quantity != ""
            else ""
        )
        updates.append(
            {
                "range": f"'{RECIPES_WORKSHEET}'!D{sheet_row}:G{sheet_row}",
                "values": [[
                    ingredient_name,
                    converted_quantity,
                    new_unit,
                    item_cost,
                ]],
            }
        )
    return updates


def render_edit_ingredient_form() -> None:
    try:
        ingredients = load_materials()
        registered_brands = load_registered_brands()
    except Exception as error:
        st.error(f"Não foi possível carregar os ingredientes: {error}")
        return

    if not ingredients:
        st.info("Ainda não existem ingredientes cadastrados.")
        return

    ingredient_by_label = {
        str(ingredient["label"]): ingredient for ingredient in ingredients
    }
    selected_label = st.selectbox(
        "Ingrediente cadastrado",
        options=list(ingredient_by_label),
        index=None,
        placeholder="Selecione um ingrediente para consultar",
        key="edit_selected_ingredient",
    )
    if not selected_label:
        st.info("Selecione um ingrediente para carregar os dados.")
        return

    selected = ingredient_by_label[selected_label]
    selected_code = str(selected["code"])
    if st.session_state.get("edit_ingredient_context") != selected_code:
        st.session_state.edit_ingredient_name = str(selected["name"])
        st.session_state.edit_ingredient_brand = str(selected["brand"])
        st.session_state.edit_ingredient_quantity = format_number_input(
            selected["purchase_quantity"]
        )
        st.session_state.edit_ingredient_unit = str(selected["unit"])
        st.session_state.edit_ingredient_price = format_number_input(selected["price"])
        st.session_state.edit_ingredient_context = selected_code

    brand_options = sorted(
        set(registered_brands) | {str(selected["brand"])},
        key=str.casefold,
    )
    with st.container(border=False, key="ingredient_edit_form_panel"):
        st.markdown(
            '<p class="form-section-title">Identificação do ingrediente</p>',
            unsafe_allow_html=True,
        )
        ingredient_column, brand_column = st.columns(2)
        with ingredient_column:
            ingredient = st.text_input("Ingrediente *", key="edit_ingredient_name")
        with brand_column:
            brand = st.selectbox(
                "Marca *",
                options=brand_options,
                accept_new_options=True,
                key="edit_ingredient_brand",
            )

        st.markdown(
            '<p class="form-section-title">Embalagem e custo</p>',
            unsafe_allow_html=True,
        )
        quantity_column, unit_column, price_column = st.columns([1, 0.8, 1])
        with quantity_column:
            quantity_text = st.text_input(
                "Quantidade *", key="edit_ingredient_quantity"
            )
        with unit_column:
            unit = st.selectbox(
                "Unidade *",
                options=("g", "kg", "ml", "l", "UN"),
                key="edit_ingredient_unit",
            )
        with price_column:
            price_text = st.text_input(
                "Valor pago (R$) *", key="edit_ingredient_price"
            )

        quantity = parse_brazilian_number(quantity_text)
        price = parse_brazilian_number(price_text)
        unit_cost = (
            price / quantity
            if price is not None and quantity is not None and quantity > 0
            else 0.0
        )
        st.markdown(
            f"""
            <div class="cost-summary">
                <div>
                    <p class="cost-summary-label">Custo por unidade de medida</p>
                    <small>Valor calculado automaticamente</small>
                </div>
                <p class="cost-summary-value">{format_currency(unit_cost)} / {unit}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        submitted = st.button(
            "Salvar alterações",
            use_container_width=True,
            key="edit_submit_ingredient",
            disabled=st.session_state.get(
                "edit_ingredient_save_in_progress", False
            ),
        )

    if not submitted:
        return

    errors = []
    if not ingredient.strip():
        errors.append("Informe o ingrediente.")
    if not brand or not brand.strip():
        errors.append("Informe a marca.")
    if quantity is None or quantity <= 0:
        errors.append("Informe uma quantidade válida e maior que zero.")
    if price is None or price <= 0:
        errors.append("Informe um valor pago válido e maior que zero.")
    if errors:
        st.error(" ".join(errors))
        return

    save_key = "edit_ingredient_save_in_progress"
    if st.session_state.get(save_key, False):
        st.warning("Alteração em andamento. Aguarde a conclusão.")
        return
    st.session_state[save_key] = True
    try:
        with MATERIAL_WRITE_LOCK:
            sheets = GoogleSheetsClient.from_streamlit_secrets()
            if material_already_exists(
                sheets,
                ingredient=ingredient,
                brand=brand,
                quantity=quantity,
                unit=unit,
                price=price,
                excluded_code=selected_code,
            ):
                st.warning(
                    "Já existe outro ingrediente com a mesma marca, quantidade, "
                    "unidade e valor pago."
                )
                return
            worksheet = sheets.worksheet(MATERIALS_WORKSHEET)
            codes = worksheet.col_values(1)
            try:
                sheet_row = codes.index(selected_code) + 1
            except ValueError:
                st.error("O ingrediente selecionado não foi encontrado na planilha.")
                return
            recipe_updates = build_ingredient_recipe_updates(
                sheets,
                selected_code,
                ingredient.strip(),
                str(selected["unit"]),
                unit,
                unit_cost,
            )
            sheets.spreadsheet().values_batch_update(
                {
                    "valueInputOption": "RAW",
                    "data": [
                        {
                            "range": (
                                f"'{MATERIALS_WORKSHEET}'!"
                                f"A{sheet_row}:G{sheet_row}"
                            ),
                            "values": [[
                                selected_code,
                                ingredient.strip(),
                                brand.strip(),
                                quantity,
                                unit,
                                price,
                                unit_cost,
                            ]],
                        },
                        *recipe_updates,
                    ],
                }
            )
        clear_app_data_cache()
    except Exception as error:
        st.error(f"Não foi possível alterar o ingrediente: {error}")
        return
    finally:
        st.session_state[save_key] = False

    st.success("Ingrediente atualizado com sucesso.")


def render_ingredient_page() -> None:
    render_page_header(
        "Ingredientes",
        "Cadastre um novo ingrediente ou consulte e altere um existente.",
    )
    new_tab, edit_tab = st.tabs(["Novo ingrediente", "Consultar e editar"])
    with new_tab:
        render_new_ingredient_form()
    with edit_tab:
        render_edit_ingredient_form()


def format_currency(value: float, decimals: int = 6) -> str:
    formatted = f"{value:,.{decimals}f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_number_input(value: object) -> str:
    if value in (None, ""):
        return ""
    number = parse_brazilian_number(str(value))
    if number is None:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}".replace(".", ",")


def initialize_recipe_items(prefix: str) -> None:
    ids_key = f"{prefix}_recipe_item_ids"
    next_key = f"{prefix}_recipe_next_item_id"
    if ids_key not in st.session_state:
        st.session_state[ids_key] = [0]
        st.session_state[next_key] = 1


def add_recipe_item(prefix: str) -> None:
    ids_key = f"{prefix}_recipe_item_ids"
    next_key = f"{prefix}_recipe_next_item_id"
    item_id = st.session_state[next_key]
    st.session_state[ids_key].append(item_id)
    st.session_state[next_key] += 1


def remove_recipe_item(prefix: str, item_id: int) -> None:
    st.session_state[f"{prefix}_recipe_item_ids"].remove(item_id)
    for field in ("material", "quantity", "remove"):
        st.session_state.pop(f"{prefix}_recipe_{field}_{item_id}", None)


def clear_recipe_editor(prefix: str) -> None:
    for key in list(st.session_state):
        if key.startswith(f"{prefix}_recipe_"):
            del st.session_state[key]
    st.session_state[f"{prefix}_recipe_item_ids"] = [0]
    st.session_state[f"{prefix}_recipe_next_item_id"] = 1
    st.session_state[f"{prefix}_recipe_name"] = ""
    st.session_state[f"{prefix}_recipe_profit"] = ""
    st.session_state[f"{prefix}_editing_recipe_photo"] = ""
    st.session_state[f"{prefix}_editing_original_item_ids"] = set()


def hydrate_recipe_editor(
    prefix: str,
    recipe: dict[str, object],
    material_by_code: dict[str, dict[str, object]],
    material_by_label: dict[str, dict[str, object]],
) -> None:
    clear_recipe_editor(prefix)
    items = list(recipe["items"])
    item_ids = list(range(len(items))) or [0]
    st.session_state[f"{prefix}_recipe_item_ids"] = item_ids
    st.session_state[f"{prefix}_recipe_next_item_id"] = len(item_ids)
    st.session_state[f"{prefix}_editing_original_item_ids"] = set(item_ids)
    st.session_state[f"{prefix}_recipe_name"] = str(recipe["name"])
    st.session_state[f"{prefix}_recipe_profit"] = str(recipe["profit"]).replace("%", "")
    st.session_state[f"{prefix}_editing_recipe_photo"] = str(recipe["photo"])

    for item_id, item in zip(item_ids, items):
        material_code = str(item["material_code"])
        material = material_by_code.get(material_code)
        if material is None:
            legacy_name = str(item["material_name"]) or "Item sem cadastro"
            legacy_label = f"⚠ Não cadastrado — {legacy_name}"
            material = {
                "code": "",
                "name": legacy_name,
                "brand": "",
                "unit": str(item["unit"]),
                "unit_cost": None,
                "label": legacy_label,
            }
            material_by_label[legacy_label] = material
        st.session_state[f"{prefix}_recipe_material_{item_id}"] = str(material["label"])
        st.session_state[f"{prefix}_recipe_quantity_{item_id}"] = format_number_input(
            item["quantity"]
        )


def add_legacy_recipe_material_options(
    recipe: dict[str, object],
    material_by_code: dict[str, dict[str, object]],
    material_by_label: dict[str, dict[str, object]],
) -> None:
    """Recria em todo rerun as opções de itens antigos ainda sem cadastro."""
    for item in recipe["items"]:
        material_code = str(item["material_code"])
        if material_code and material_code in material_by_code:
            continue
        legacy_name = str(item["material_name"]) or "Item sem cadastro"
        legacy_label = f"⚠ Não cadastrado — {legacy_name}"
        material_by_label.setdefault(
            legacy_label,
            {
                "code": "",
                "name": legacy_name,
                "brand": "",
                "purchase_quantity": None,
                "price": None,
                "unit": str(item["unit"]),
                "unit_cost": None,
                "label": legacy_label,
            },
        )


def recipe_name_exists(
    sheets: GoogleSheetsClient,
    name: str,
    excluded_code: str | None = None,
) -> bool:
    rows = sheets.worksheet(RECIPES_WORKSHEET).get_all_values()[1:]
    normalized_name = normalize_text(name)
    return any(
        len(row) > 1
        and row[0].strip() != (excluded_code or "")
        and normalize_text(row[1]) == normalized_name
        for row in rows
    )


def replace_recipe_rows(
    sheets: GoogleSheetsClient,
    recipe_code: str,
    new_rows: list[list[object]],
) -> None:
    """Atualiza somente as linhas da receita selecionada."""
    worksheet = sheets.worksheet(RECIPES_WORKSHEET)
    current_rows = worksheet.get_all_values()[1:]
    recipe_sheet_rows = [
        sheet_row
        for sheet_row, row in enumerate(current_rows, start=2)
        if row and row[0].strip() == recipe_code
    ]
    if not recipe_sheet_rows:
        raise RuntimeError("A receita selecionada não foi encontrada na planilha.")

    shared_count = min(len(recipe_sheet_rows), len(new_rows))
    updates = [
        {
            "range": f"A{sheet_row}:I{sheet_row}",
            "values": [new_rows[position]],
        }
        for position, sheet_row in enumerate(recipe_sheet_rows[:shared_count])
    ]
    updates.extend(
        {
            "range": f"A{sheet_row}:I{sheet_row}",
            "values": [[""] * 9],
        }
        for sheet_row in recipe_sheet_rows[shared_count:]
    )
    if updates:
        worksheet.batch_update(updates, value_input_option="RAW")

    additional_rows = new_rows[shared_count:]
    if additional_rows:
        worksheet.append_rows(
            additional_rows,
            value_input_option="RAW",
        )


def render_recipe_form() -> None:
    render_page_header(
        "Receitas",
        "Cadastre uma nova receita ou consulte e altere uma receita existente.",
    )
    new_recipe_tab, edit_recipe_tab = st.tabs(
        ["Nova receita", "Consultar e editar"]
    )
    with new_recipe_tab:
        render_recipe_editor(editing_mode=False, prefix="new")
    with edit_recipe_tab:
        render_recipe_editor(editing_mode=True, prefix="edit")


def render_recipe_editor(editing_mode: bool, prefix: str) -> None:
    try:
        materials = load_materials()
        existing_recipes = load_existing_recipes()
    except Exception as error:
        st.error(f"Não foi possível carregar os dados das receitas: {error}")
        return

    if not materials:
        st.warning("Cadastre ao menos um ingrediente antes de criar receitas.")
        return

    material_by_label = {str(item["label"]): item for item in materials}
    material_by_code = {str(item["code"]): item for item in materials}
    editing_recipe: dict[str, object] | None = None
    editing_code: str | None = None

    if editing_mode:
        if not existing_recipes:
            st.info("Ainda não existem receitas cadastradas.")
            return
        recipe_by_label = {
            f"{recipe['name']} (cód. {recipe['code']})": recipe
            for recipe in existing_recipes
        }
        selected_recipe_label = st.selectbox(
            "Receita cadastrada",
            options=list(recipe_by_label),
            index=None,
            placeholder="Selecione uma receita para consultar",
            key=f"{prefix}_selected_recipe_to_edit",
        )
        if not selected_recipe_label:
            st.info("Selecione uma receita para carregar os dados.")
            return
        editing_recipe = recipe_by_label[selected_recipe_label]
        editing_code = str(editing_recipe["code"])
        add_legacy_recipe_material_options(
            editing_recipe,
            material_by_code,
            material_by_label,
        )
        editor_context = f"edit:{editing_code}"
        context_key = f"{prefix}_recipe_editor_context"
        if st.session_state.get(context_key) != editor_context:
            hydrate_recipe_editor(
                prefix,
                editing_recipe,
                material_by_code,
                material_by_label,
            )
            st.session_state[context_key] = editor_context
    else:
        context_key = f"{prefix}_recipe_editor_context"
        if st.session_state.get(context_key) != "new":
            clear_recipe_editor(prefix)
            st.session_state[context_key] = "new"

    initialize_recipe_items(prefix)
    material_labels = list(material_by_label)
    recipe_items: list[dict[str, object]] = []

    with st.container(border=False, key=f"recipe_form_panel_{prefix}"):
        st.markdown(
            '<p class="form-section-title">Identificação da receita</p>',
            unsafe_allow_html=True,
        )
        name_column, profit_column = st.columns([2, 1])
        with name_column:
            recipe_name = st.text_input(
                "Nome da receita *",
                placeholder="Ex.: Brigadeiro tradicional",
                key=f"{prefix}_recipe_name",
            )
        with profit_column:
            profit_text = st.text_input(
                "Taxa de lucro (%) *",
                placeholder="Ex.: 10",
                key=f"{prefix}_recipe_profit",
            )

        st.markdown(
            '<p class="form-section-title">Foto da receita</p>',
            unsafe_allow_html=True,
        )
        current_photo = str(
            st.session_state.get(f"{prefix}_editing_recipe_photo", "")
        ).strip()
        photo_column, preview_column = st.columns([2, 1])
        with photo_column:
            uploaded_photo = st.file_uploader(
                "Imagem da receita",
                type=("jpg", "jpeg", "png", "webp"),
                help="Formatos permitidos: JPG, PNG e WebP. Tamanho máximo: 10 MB.",
                key=f"{prefix}_recipe_photo_upload",
            )
            if editing_code and current_photo:
                st.caption(
                    "Envie uma nova imagem somente se desejar substituir a foto atual."
                )
            else:
                st.caption("A foto é opcional e poderá ser adicionada posteriormente.")
        with preview_column:
            if uploaded_photo is not None:
                st.image(
                    uploaded_photo,
                    caption="Nova foto",
                    use_container_width=True,
                )
            elif current_photo:
                st.image(
                    current_photo,
                    caption="Foto atual",
                    use_container_width=True,
                )

        st.markdown(
            '<p class="form-section-title">Ingredientes utilizados</p>',
            unsafe_allow_html=True,
        )

        item_ids_key = f"{prefix}_recipe_item_ids"
        for position, item_id in enumerate(
            list(st.session_state[item_ids_key]),
            start=1,
        ):
            with st.container(
                border=False,
                key=f"recipe_item_{prefix}_{item_id}",
            ):
                st.markdown(f"**Ingrediente {position}**")
                material_column, quantity_column, action_column = st.columns(
                    [3, 1.15, 0.75],
                    vertical_alignment="bottom",
                )
                with material_column:
                    selected_label = st.selectbox(
                        "Ingrediente *",
                        options=material_labels,
                        index=None,
                        placeholder="Selecione um ingrediente",
                        key=f"{prefix}_recipe_material_{item_id}",
                    )

                selected_material = (
                    material_by_label.get(selected_label) if selected_label else None
                )
                selected_unit = str(selected_material["unit"]) if selected_material else "—"

                with quantity_column:
                    quantity_text = st.text_input(
                        f"Quantidade ({selected_unit}) *",
                        placeholder="Ex.: 200",
                        key=f"{prefix}_recipe_quantity_{item_id}",
                    )
                with action_column:
                    remove_clicked = st.button(
                        "Remover",
                        key=f"{prefix}_recipe_remove_{item_id}",
                        use_container_width=True,
                        disabled=len(st.session_state[item_ids_key]) == 1,
                    )

                if remove_clicked:
                    remove_recipe_item(prefix, item_id)
                    st.rerun()

                used_quantity = parse_brazilian_number(quantity_text)
                item_cost = 0.0
                unit_cost = selected_material.get("unit_cost") if selected_material else None
                if unit_cost is not None and used_quantity is not None and used_quantity > 0:
                    item_cost = float(unit_cost) * used_quantity

                st.markdown(
                    f'<p style="margin:0;text-align:right;font-weight:800">'
                    f'Custo do item: {format_currency(item_cost)}</p>',
                    unsafe_allow_html=True,
                )
                recipe_items.append(
                    {
                        "item_id": item_id,
                        "material": selected_material,
                        "quantity": used_quantity,
                        "cost": item_cost,
                    }
                )

        if st.button(
            "Adicionar ingrediente",
            key=f"{prefix}_add_recipe_item",
            use_container_width=True,
        ):
            add_recipe_item(prefix)
            st.rerun()

        total_cost = sum(float(item["cost"]) for item in recipe_items)
        st.markdown(
            f"""
            <div class="cost-summary">
                <div>
                    <p class="cost-summary-label">Custo total da receita</p>
                    <small>Soma de todos os ingredientes</small>
                </div>
                <p class="cost-summary-value">{format_currency(total_cost)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        submitted = st.button(
            "Salvar alterações" if editing_code else "Cadastrar receita",
            key=f"{prefix}_submit_recipe",
            use_container_width=True,
            disabled=st.session_state.get(
                f"{prefix}_recipe_save_in_progress",
                False,
            ),
        )

    if not submitted:
        return

    profit_rate = parse_brazilian_number(profit_text.replace("%", ""))
    errors: list[str] = []
    if not recipe_name.strip():
        errors.append("Informe o nome da receita.")
    if profit_rate is None or profit_rate < 0:
        errors.append("Informe uma taxa de lucro válida.")
    if uploaded_photo is not None and uploaded_photo.size > 10 * 1024 * 1024:
        errors.append("A foto da receita deve ter no máximo 10 MB.")
    selected_codes: list[str] = []
    for position, item in enumerate(recipe_items, start=1):
        material = item["material"]
        quantity = item["quantity"]
        if material is None:
            errors.append(f"Selecione o ingrediente {position}.")
            continue
        if quantity is None or float(quantity) <= 0:
            errors.append(f"Informe uma quantidade válida no ingrediente {position}.")
        identity = str(material["code"]) or normalize_text(str(material["name"]))
        selected_codes.append(identity)
    if len(selected_codes) != len(set(selected_codes)):
        errors.append("O mesmo ingrediente não pode ser adicionado duas vezes.")

    if errors:
        st.error(" ".join(errors))
        return

    save_state_key = f"{prefix}_recipe_save_in_progress"
    if st.session_state.get(save_state_key, False):
        st.warning("Cadastro em andamento. Aguarde a conclusão.")
        return

    st.session_state[save_state_key] = True
    uploaded_image = None
    sheet_saved = False
    try:
        with RECIPE_WRITE_LOCK:
            sheets = GoogleSheetsClient.from_streamlit_secrets()
            if recipe_name_exists(sheets, recipe_name, excluded_code=editing_code):
                st.warning("Já existe uma receita cadastrada com esse nome.")
                return
            recipe_code = editing_code or str(
                sheets.next_integer_code(RECIPES_WORKSHEET)
            )
            photo_url = current_photo
            if uploaded_photo is not None:
                uploaded_image = upload_recipe_image(
                    uploaded_photo,
                    recipe_code,
                    recipe_name.strip(),
                )
                photo_url = uploaded_image.url
            percent_value = f"{profit_rate:g}%".replace(".", ",")
            rows = []
            for position, item in enumerate(recipe_items):
                material = item["material"]
                quantity = item["quantity"]
                unit_cost = material.get("unit_cost")
                item_cost: float | str = (
                    float(unit_cost) * float(quantity)
                    if unit_cost is not None and quantity is not None
                    else ""
                )
                rows.append(
                    [
                        recipe_code,
                        recipe_name.strip(),
                        material["code"],
                        material["name"],
                        quantity if quantity is not None else "",
                        material["unit"],
                        item_cost,
                        percent_value,
                        (
                            photo_url
                            if position == 0
                            else ""
                        ),
                    ]
                )
            if editing_code:
                replace_recipe_rows(sheets, editing_code, rows)
            else:
                sheets.append_rows(RECIPES_WORKSHEET, rows)
            sheet_saved = True
            clear_app_data_cache()
    except Exception as error:
        if uploaded_image is not None and not sheet_saved:
            try:
                delete_recipe_image(uploaded_image.public_id)
            except Exception:
                pass
        st.error(f"Não foi possível salvar a receita: {error}")
        return
    finally:
        st.session_state[save_state_key] = False

    action = "atualizada" if editing_code else "cadastrada"
    if uploaded_image is not None and current_photo:
        try:
            delete_recipe_image(current_photo, is_url=True)
        except Exception:
            st.warning(
                "A receita foi salva, mas não foi possível remover a foto antiga "
                "do armazenamento."
            )
    st.success(
        f"Receita {action} com sucesso. Código: {recipe_code}. "
        f"Custo total: {format_currency(total_cost)}."
    )


page = st.query_params.get("pagina", "inicio")
if isinstance(page, list):
    page = page[0] if page else "inicio"

render_sidebar(page)
if page in {"materia-prima", "ingredientes"}:
    render_ingredient_page()
elif page == "receitas":
    render_recipe_form()
elif page == "receitas-nova":
    render_recipe_form()
elif page == "receitas-consultar":
    render_recipe_form()
else:
    render_home()
