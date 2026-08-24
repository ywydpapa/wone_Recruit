import math


def calc_levy(employee_count: int, disabled_count: int, rates: dict) -> dict:
    # 장애인 고용부담금 계산
    quota_rate = rates.get("quota_rate_private", 0.031)
    levy_per = rates.get("levy_per_person_month", 1310000)
    inc_min = rates.get("incentive_min", 350000)
    inc_max = rates.get("incentive_max", 900000)

    mandatory = math.floor(employee_count * quota_rate) if employee_count >= 50 else 0
    shortfall = max(0, mandatory - disabled_count)
    surplus = max(0, disabled_count - mandatory)

    levy_applicable = employee_count >= 100
    monthly_levy = shortfall * levy_per if levy_applicable else 0
    annual_levy = monthly_levy * 12

    monthly_incentive_min = surplus * inc_min if mandatory > 0 and surplus > 0 else 0
    monthly_incentive_max = surplus * inc_max if mandatory > 0 and surplus > 0 else 0

    return {
        "employee_count": employee_count,
        "disabled_count": disabled_count,
        "mandatory": mandatory,
        "quota_rate": quota_rate,
        "shortfall": shortfall,
        "surplus": surplus,
        "levy_applicable": levy_applicable,
        "monthly_levy": monthly_levy,
        "annual_levy": annual_levy,
        "monthly_incentive_min": monthly_incentive_min,
        "monthly_incentive_max": monthly_incentive_max,
    }
