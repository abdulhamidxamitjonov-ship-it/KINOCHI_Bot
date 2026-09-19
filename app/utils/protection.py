"""Telegram content-protection helpers.

Content protection is applied only when sending protected movie/series media to
ordinary users. Admins are intentionally exempt, as required by the bot owner.
"""


def protect_for_user(user_id: int, admin_ids: set[int]) -> bool:
    return user_id not in admin_ids
