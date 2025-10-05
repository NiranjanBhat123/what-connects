import random
import string


def generate_code(length=6, uppercase=True):
    """Generate a random alphanumeric code."""
    chars = string.ascii_uppercase + string.digits if uppercase else string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip