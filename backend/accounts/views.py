from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .http import error, json_body
from .models import Client
from .profile import build_profile
from .resumes import ResumeError, extract_text, is_safe_email, store_resume, validate_pdf
from .tokens import issue_token

MIN_PASSWORD_LENGTH = 8
INFO_FIELDS = ("full_name", "phone", "location", "linkedin", "github", "website", "work_authorization")


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


@csrf_exempt
@require_POST
def client_signup(request):
    email = _text(request.POST.get("email")).lower()
    password = request.POST.get("password", "")
    resume = request.FILES.get("resume")
    if not is_safe_email(email):
        return error("A valid email address is required.")
    if len(password) < MIN_PASSWORD_LENGTH:
        return error(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.")
    if resume is None:
        return error("A PDF resume is required.")
    if resume.size > settings.MAX_RESUME_BYTES:
        return error("Resume is larger than the 5 MB limit.")
    if Client.objects.filter(email=email).exists():
        return error("This email is already registered.", 409)

    data = resume.read()
    try:
        validate_pdf(data)
    except ResumeError as exc:
        return error(str(exc))

    info = {key: _text(request.POST.get(key)) for key in INFO_FIELDS}
    info = {key: value for key, value in info.items() if value}
    info["email"] = email
    resume_text = extract_text(data)
    client = Client(email=email, info=info, resume_text=resume_text, profile=build_profile(info, resume_text))
    client.set_password(password)
    client.resume_path = str(store_resume(email, data))
    try:
        client.save()
    except IntegrityError:
        return error("This email is already registered.", 409)
    return JsonResponse({"token": issue_token("client", client.id), "email": email}, status=201)


@csrf_exempt
@require_POST
def client_signin(request):
    body = json_body(request)
    client = Client.objects.filter(email=_text(body.get("email")).lower()).first()
    if client is None or not client.check_password(str(body.get("password", ""))):
        return error("Incorrect email or password.", 401)
    return JsonResponse({"token": issue_token("client", client.id), "email": client.email})


@csrf_exempt
@require_POST
def boss_signup(request):
    body = json_body(request)
    username, password = _text(body.get("username")), str(body.get("password", ""))
    if not settings.BOSS_KEY or not constant_time_compare(str(body.get("boss_key", "")), settings.BOSS_KEY):
        return error("Invalid boss key.", 403)
    if not username or len(password) < MIN_PASSWORD_LENGTH:
        return error(f"A username and a password of at least {MIN_PASSWORD_LENGTH} characters are required.")
    users = get_user_model().objects
    if users.filter(username=username).exists():
        return error("This username is already taken.", 409)
    user = users.create_user(username=username, password=password, is_staff=True)
    return JsonResponse({"token": issue_token("boss", user.id), "username": username}, status=201)


@csrf_exempt
@require_POST
def boss_signin(request):
    body = json_body(request)
    user = authenticate(username=_text(body.get("username")), password=str(body.get("password", "")))
    if user is None or not user.is_staff:
        return error("Incorrect username or password.", 401)
    return JsonResponse({"token": issue_token("boss", user.id), "username": user.username})
