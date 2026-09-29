import logging
import time
import uuid
from django.conf import settings

audit_logger = logging.getLogger("activity_audit")


def get_client_ip(request):
    """
    Extracts the real client IP address considering edge proxy headers
    (Cloudflare, Nginx, AWS ALB, and standard reverse proxies).
    """
    # Cloudflare Header
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip.strip()

    # Nginx / Proxy Header
    real_ip = request.META.get("HTTP_X_REAL_IP")
    if real_ip:
        return real_ip.strip()

    # Standard Load Balancer / Proxy Header
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "127.0.0.1")


class RequestCorrelationMiddleware:
    """
    Enterprise Request Correlation Middleware.
    Assigns a unique X-Request-ID to every request for trace-level request tracking across distributed systems.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Obtain existing request ID or generate a new UUID4
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.id = request_id

        response = self.get_response(request)

        # Attach X-Request-ID to response headers for client/frontend correlation
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware:
    """
    Enterprise Security Headers Middleware.
    Enforces strict security headers across all API responses (X-Content-Type-Options, X-Frame-Options, HSTS, etc.).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not getattr(settings, "DEBUG", True):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


class AuditLoggingMiddleware:
    """
    Enterprise Activity Audit Middleware.
    Logs user activity, IP address, endpoint URL, HTTP method, response status, and duration in a fail-safe manner.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Fail-safe audit logging wrapper to prevent logging errors from breaking requests
        try:
            path = request.path
            if path.startswith("/api/"):
                ip_address = get_client_ip(request)
                request_id = getattr(request, "id", "N/A")

                # Extract Client & User Details safely
                user_obj = getattr(request, "user_obj", None) or getattr(
                    request, "user", None
                )
                username = "Anonymous"
                if user_obj and hasattr(user_obj, "username") and user_obj.username:
                    username = user_obj.username
                elif (
                    user_obj
                    and hasattr(user_obj, "is_authenticated")
                    and user_obj.is_authenticated
                ):
                    username = str(user_obj)

                method = request.method
                status_code = response.status_code

                log_entry = (
                    f"ReqID: {request_id} | User: {username} | IP: {ip_address} | "
                    f"Method: {method} | Path: {path} | Status: {status_code} | Duration: {duration_ms}ms"
                )

                if status_code >= 500:
                    audit_logger.error(log_entry)
                elif status_code >= 400:
                    audit_logger.warning(log_entry)
                else:
                    audit_logger.info(log_entry)
        except Exception as log_err:
            audit_logger.warning(f"Audit log processing failed: {log_err}")

        return response
