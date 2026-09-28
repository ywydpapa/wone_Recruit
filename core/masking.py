def mask_name(name):
    if not name:
        return "-"
    n = len(name)
    if n <= 1:
        return "*"
    if n == 2:
        return name[0] + "*"
    return name[0] + "*" * (n - 2) + name[-1]


def mask_phone(phone):
    if not phone:
        return "-"
    # 010-1234-5678 -> 010-****-5678
    parts = phone.replace(" ", "").split("-")
    if len(parts) == 3:
        return f"{parts[0]}-****-{parts[2]}"
    digits = phone.replace("-", "").replace(" ", "")
    if len(digits) >= 8:
        return digits[:3] + "-****-" + digits[-4:]
    return "*" * len(phone)


def mask_email(email):
    if not email:
        return "-"
    at = email.find("@")
    if at <= 0:
        return email
    local = email[:at]
    domain = email[at:]
    if len(local) <= 3:
        return local[0] + "***" + domain
    return local[:3] + "***" + domain
