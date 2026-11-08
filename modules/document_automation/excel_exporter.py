"""Write extracted PDF tables to a multi-sheet Excel workbook."""
import re

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def _safe_sheet_title(value, fallback):
    title = re.sub(r"[\\/*?:\[\]]", " ", str(value or "")).strip()
    return (title[:31] or fallback)


def _unique_headers(header_row, width):
    headers = []
    used = set()
    for index in range(width):
        value = str(header_row[index] or "").strip() if index < len(header_row) else ""
        value = value or f"Column {index + 1}"
        base = value
        suffix = 2
        while value.casefold() in used:
            value = f"{base} ({suffix})"
            suffix += 1
        used.add(value.casefold())
        headers.append(value)
    return headers


def export_tables_to_excel(tables, output_path):
    """Export each detected table to its own worksheet."""
    if not tables:
        raise ValueError("There are no extracted tables to export.")

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)
    used_titles = set()

    for table_index, table in enumerate(tables, start=1):
        rows = table.get("rows") or []
        if not rows:
            continue

        width = max(len(row) for row in rows)
        headers = _unique_headers(rows[0], width)
        base_title = _safe_sheet_title(
            f"Page {table.get('page', table_index)} Table {table_index}",
            f"Table {table_index}",
        )
        title = base_title
        suffix = 2
        while title.casefold() in used_titles:
            ending = f" {suffix}"
            title = f"{base_title[:31 - len(ending)]}{ending}"
            suffix += 1
        used_titles.add(title.casefold())

        sheet = workbook.create_sheet(title=title)
        sheet.append(headers)
        for row in rows[1:]:
            values = list(row) + [None] * (width - len(row))
            sheet.append(values[:width])

        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="3154C5")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        for column_index in range(1, width + 1):
            values = [
                len(str(sheet.cell(row=row_index, column=column_index).value or ""))
                for row_index in range(1, min(sheet.max_row, 100) + 1)
            ]
            width_hint = min(max(max(values, default=10) + 2, 12), 42)
            sheet.column_dimensions[get_column_letter(column_index)].width = width_hint

    if not workbook.sheetnames:
        raise ValueError("No non-empty tables were available to export.")

    workbook.save(output_path)
    return output_path
