import os
import re

import httpx

from core.logger import log

_API_URL = "https://api.odcloud.kr/api/nts-businessman/v1/validate"


def _clean(biz_no):
    return re.sub(r"[^0-9]", "", biz_no)


async def check_bizno(biz_no):
    cleaned = _clean(biz_no)
    if len(cleaned) != 10:
        return False

    api_key = os.getenv("BIZNO_API_KEY")
    if not api_key:
        log.warning("BIZNO_API_KEY 미설정, 검증 건너뜀")
        return None

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _API_URL,
                params={"serviceKey": api_key},
                json={"businesses": [{"b_no": cleaned, "start_dt": "", "p_nm": "", "p_nm2": "", "b_nm": "", "corp_no": "", "b_sector": "", "b_type": "", "b_adr": ""}]},
            )
            data = resp.json()
            return data["data"][0]["valid"] == "01"
    except Exception as e:
        log.warning("사업자번호 API 호출 실패: %s", e)
        return None
