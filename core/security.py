import re

import bcrypt

MIN_PASSWORD_LENGTH = 12

# 유출 사전 상위 비밀번호 및 키보드 배열 패턴임
_COMMON = {
    "password1234", "password123!", "passw0rd1234", "qwerty123456", "qwer1234qwer",
    "qwer1234!@#$", "1q2w3e4r5t6y", "1qaz2wsx3edc", "asdf1234asdf", "admin1234567",
    "abcd12345678", "abc123456789", "123456789abc", "iloveyou1234", "qwertyuiop12",
    "zxcvbnm12345", "a1b2c3d4e5f6", "1234567890ab", "123456789012a",
}


def check_password(pw):
    if len(pw) < MIN_PASSWORD_LENGTH:
        return "short"
    if re.search(r"\s", pw):
        return "space"
    if not re.fullmatch(r"[!-~]+", pw):
        return "charset"
    kinds = bool(re.search(r"[A-Za-z]", pw)) + bool(re.search(r"[0-9]", pw)) + bool(re.search(r"[^A-Za-z0-9]", pw))
    if kinds < 2:
        return "weak"
    if pw.lower() in _COMMON or len(set(pw)) <= 3:
        return "common"
    return None


def hash_password(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())
