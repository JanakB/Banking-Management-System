from typing import Dict


def is_admin_user(request) -> Dict[str, bool]:
    user = getattr(request, 'user', None)
    is_admin = False
    try:
        if user and user.is_authenticated:
            if getattr(user, 'is_superuser', False):
                is_admin = True
            else:
                profile = getattr(user, 'profile', None)
                if profile and getattr(profile, 'role', None) == 'admin':
                    is_admin = True
    except Exception:
        is_admin = False
    return {'is_bank_admin': is_admin}

