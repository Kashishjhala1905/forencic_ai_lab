"""Configurable field-extraction rules.

Each rule: kind (date|amount|id|text), types (document types it applies to), patterns (regex TIERS tried in
priority order: the first tier that matches decides the value), single (True => several different values in the
same tier are reported as a conflict). Edit this file to add fields; no other code changes are needed.
"""
DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[ ]+[A-Za-z]{3,9}\.?,?[ ]+\d{4}|[A-Za-z]{3,9}\.?[ ]+\d{1,2},?[ ]+\d{4})"
AMT = r"(?:[$€£₹]|Rs\.?|INR|USD|EUR|GBP)?[ \t]*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
SEP = r"[ \t]*[:\-#]?[ \t]*"
ALL = ["invoice", "id_card", "certificate", "bank_statement", "general"]
LINE = r"(.{2,80}?)[ \t]*$"

FIELD_RULES = {
    "person_or_org_name": {"label": "Person / organization name", "kind": "text", "types": ALL, "single": False, "patterns": [
        r"(?im)^[ \t]*(?:full[ \t]+|student[ \t]+|candidate(?:'s)?[ \t]+|account[ \t]+holder[ \t]+|holder[ \t]+)?name(?:[ \t]+of[ \t]+(?:the[ \t]+)?(?:candidate|student|holder))?" + SEP + LINE,
        r"(?im)^[ \t]*(?:bill(?:ed)?[ \t]+to|customer|issued[ \t]+to|account[ \t]+holder|this[ \t]+is[ \t]+to[ \t]+certify[ \t]+that)" + SEP + LINE]},
    "document_number": {"label": "Document number", "kind": "id", "types": ["id_card", "certificate", "general"], "single": True, "patterns": [
        r"(?i)\b(?:document|doc|id|card|licen[cs]e|passport|certificate|roll|registration|reg|enrol(?:l)?ment|serial)[ \t]*(?:no\.?|number|num)\b" + SEP + r"([A-Z0-9][A-Z0-9\-/]{3,})"]},
    "invoice_number": {"label": "Invoice number", "kind": "id", "types": ["invoice"], "single": True, "patterns": [
        r"(?i)\b(?:invoice|receipt|bill)[ \t]*(?:no\.?|number|num|#)" + SEP + r"([A-Z0-9][A-Z0-9\-/]{2,})"]},
    "account_number": {"label": "Account number", "kind": "id", "types": ["bank_statement"], "single": True, "patterns": [
        r"(?i)\baccount[ \t]*(?:no\.?|number|num|#)" + SEP + r"([A-Z0-9Xx*][A-Z0-9Xx*\-]{5,})"]},
    "date_of_birth": {"label": "Date of birth", "kind": "date", "types": ["id_card", "general"], "single": True, "patterns": [
        r"(?i)\b(?:date[ \t]+of[ \t]+birth|d\.?o\.?b\.?|born)\b" + SEP + DATE]},
    "issue_date": {"label": "Date of issue", "kind": "date", "types": ALL, "single": True, "patterns": [
        r"(?i)\b(?:date[ \t]+of[ \t]+issue|issue[ \t]+date|issued[ \t]+on|date[ \t]+issued|invoice[ \t]+date|statement[ \t]+date|date[ \t]+of[ \t]+(?:result|declaration))\b" + SEP + DATE,
        r"(?im)^[ \t]*date" + SEP + DATE]},
    "expiry_date": {"label": "Expiry date", "kind": "date", "types": ["id_card", "certificate", "general"], "single": True, "patterns": [
        r"(?i)\b(?:date[ \t]+of[ \t]+expiry|expiry[ \t]+date|expiration[ \t]+date|expires(?:[ \t]+on)?|valid[ \t]+(?:until|till|upto|through))\b" + SEP + DATE]},
    "due_date": {"label": "Payment due date", "kind": "date", "types": ["invoice"], "single": True, "patterns": [
        r"(?i)\b(?:due[ \t]+date|payment[ \t]+due(?:[ \t]+date)?|pay[ \t]+by)\b" + SEP + DATE]},
    "subtotal": {"label": "Subtotal", "kind": "amount", "types": ["invoice"], "single": True, "patterns": [
        r"(?i)\bsub[ \t]*-?[ \t]*total\b" + SEP + AMT]},
    "tax_amount": {"label": "Tax amount", "kind": "amount", "types": ["invoice"], "single": False, "sum_multiple": True, "patterns": [
        r"(?i)\b(?:total[ \t]+(?:tax|gst|vat)|tax[ \t]+amount)\b" + SEP + AMT,
        r"(?i)\b(?:tax|gst|vat|igst|cgst|sgst)\b(?:[ \t]*\(?[0-9.]+[ \t]*%\)?)?" + SEP + AMT]},
    "total_amount": {"label": "Total amount", "kind": "amount", "types": ["invoice", "general"], "single": True, "patterns": [
        r"(?i)\b(?:grand[ \t]+total|total[ \t]+amount(?:[ \t]+due)?|amount[ \t]+due|total[ \t]+due|balance[ \t]+due)\b" + SEP + AMT,
        r"(?i)(?<![a-z])total\b" + SEP + AMT]},
    "opening_balance": {"label": "Opening balance", "kind": "amount", "types": ["bank_statement"], "single": True, "patterns": [
        r"(?i)\bopening[ \t]+balance\b" + SEP + AMT]},
    "closing_balance": {"label": "Closing balance", "kind": "amount", "types": ["bank_statement"], "single": True, "patterns": [
        r"(?i)\bclosing[ \t]+balance\b" + SEP + AMT]},
    "institution": {"label": "Institution / issuer", "kind": "text", "types": ["certificate", "id_card"], "single": False, "patterns": [
        r"(?im)^(.{0,60}\b(?:university|institute|college|school|board|authority|department)\b.{0,60})$"]},
    "result": {"label": "Result / grade", "kind": "text", "types": ["certificate"], "single": False, "patterns": [
        r"(?i)\b(?:cgpa|percentage|grade|result|marks[ \t]+obtained)\b" + SEP + r"([A-Za-z0-9.+/% ]{1,20}?)[ \t]*$"]},
    "address": {"label": "Address", "kind": "text", "types": ALL, "single": False, "patterns": [
        r"(?im)^[ \t]*address" + SEP + r"(.{5,120}?)[ \t]*$"]},
}

REQUIRED_FIELDS = {
    "invoice": ["invoice_number", "issue_date", "total_amount", "person_or_org_name"],
    "id_card": ["person_or_org_name", "document_number", "date_of_birth"],
    "certificate": ["person_or_org_name", "institution", "document_number"],
    "bank_statement": ["person_or_org_name", "account_number"],
    "general": [],
}

TYPE_KEYWORDS = {
    "invoice": ["invoice", "bill to", "subtotal", "sub total", "gst", "vat", "total due", "amount due", "receipt", "tax"],
    "id_card": ["identity", "id card", "date of birth", "dob", "passport", "driving licen", "national id", "identification"],
    "certificate": ["certificate", "marksheet", "mark sheet", "certify", "cgpa", "university", "examination", "roll no", "grade"],
    "bank_statement": ["statement of account", "account number", "opening balance", "closing balance", "debit", "credit", "ifsc", "bank"],
}
