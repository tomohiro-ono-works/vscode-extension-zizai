"""Read a bounded Excel sample and sheet list for the row selection form."""


def read_preview_rows(path, settings, *, max_rows, max_cols):
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook[settings['sheet_name']]
        return list(sheet.iter_rows(max_row=min(sheet.max_row or max_rows, max_rows),
                                    max_col=min(sheet.max_column or max_cols, max_cols), values_only=True))
    finally:
        workbook.close()


def sheet_names(path):
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return workbook.sheetnames
    finally:
        workbook.close()
