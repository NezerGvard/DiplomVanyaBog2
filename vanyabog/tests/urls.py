from django.urls import include, path, re_path
from .views import *

urlpatterns = [
    path("", Main.as_view(), name='main'),
    path("ai", AiGenerateFile.as_view(), name='ai'),
    path('redacted/<str:uuid>', RedactedTest.as_view()),
    path('account/register', Register.as_view()),
    path('account/login', Login.as_view()),
    path('account/logout', Logout.as_view()),
    path('account/profile', Profile.as_view()),
]