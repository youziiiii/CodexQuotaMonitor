def quota_state(remaining: int, limit: int) -> str:
    if limit <= 0:
        return "unknown"
    ratio = remaining / limit
    if ratio < 0.10:
        return "critical"
    if ratio < 0.20:
        return "warning"
    return "normal"
