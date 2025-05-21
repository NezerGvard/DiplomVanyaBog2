import os
import pprint
from typing import Tuple
from django.views import View
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from asgiref.sync import sync_to_async

from django.conf import settings

from .forms import TestForm
from .models import Test, UserFile
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from .handlers import *
import asyncio

@sync_to_async
def save_test_instance(form) -> Test:
    """Сохраняем форму и возвращаем созданный объект Тest."""
    instance = form.save(commit=False)
    instance.save()
    return instance

@sync_to_async
def save_user_file(user: User, file: Test):
    UserFile.objects.create(user=user, file=file)

@sync_to_async
def get_all_tests():
    """Возвращает list(Test) — безопасно в async‑коде."""
    return list(Test.objects.all())

class Main(View):
    template_name = "main.html"

    async def get(self, request: HttpRequest):
        is_authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
        return render(request, self.template_name, {"is_authenticated": is_authenticated})


class AiGenerateFile(View):
    template_name = "ai.html"

    async def get(self, request: HttpRequest):
        form = TestForm()
        is_authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
        return render(request, self.template_name, {"form": form, "is_authenticated": is_authenticated})

    async def post(self, request: HttpRequest):
        form = TestForm(request.POST, request.FILES)

        if not form.is_valid():
            redirect('/ai')

        test_instance = await save_test_instance(form)
        is_authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
        await save_user_file(request.user if is_authenticated else None, test_instance)
        file_id = str(test_instance.id).replace("-", "")
        question_count = request.POST.get("question_count", "")
        field_type = request.POST.get("field_type", "")
        difficulty = request.POST.get("difficulty", "")
        text = ReadFile().read(test_instance)
        user_prompt = request.POST.get("question_prompt", "")
        prompt = Prompt(
            prompt=user_prompt, 
            q_text_prompt=text, 
            question_count=question_count,
            field_type=field_type,
            difficulty=difficulty
            ).get()
        print(prompt)
        answer = await ask_mistral(str(prompt))
        correct_output_ai = answer.split('```json')[1].split('```')[0]
        print(correct_output_ai)
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'json')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, f'{str(test_instance.id).replace("-", "")}.json')

        json_object = json.loads(correct_output_ai)
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(json_object, file, ensure_ascii=False, indent=4)
            
        return redirect(f"/redacted/{file_id}")

def redacted_test_keys(element: str):
    if '_' not in element:
        return element
    return element.split('_')[0]

class RedactedTest(View):
    def get(self, request: HttpRequest, uuid: 'str'):
        file = Test.objects.filter(id=uuid)[0]
        form = Fabric(file).generate()
        is_authenticated = request.user.is_authenticated
        return render(request, 'redacted.html', {'form': form, 'is_authenticated': is_authenticated})
    
    def post(self, request: HttpRequest, uuid: 'str'):
        form = dict(request.POST)
        print(form.keys())
        keys = list(set(list(map(redacted_test_keys, form.keys()))))
        print(keys)
        if 'csrfmiddlewaretoken' in keys:
            keys.remove('csrfmiddlewaretoken')
        list_questions_data = []
        for index, values in enumerate(keys):
            if 'o-' in values or 'q' not in values:
                continue
            questions_data = {}
            questions_data['id'] = values
            questions_data['difficulty'] = form[f'{values}_difficulty'][0]
            questions_data['question'] = form[values][0]
            questions_data['right'] = form[f'{values}_right'][0]
            questions_data['hint'] = form[f'{values}_hint'][0]
            questions_data['explanation'] = form[f'{values}_explanation'][0]
            questions_data['options'] = [form[f'{values}_{i}'][0] for i in range(0, 4)]
            list_questions_data.append(questions_data)
        model = Test.objects.filter(id=uuid)[0]
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'json')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f'{str(model.id).replace("-", "")}.json')
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = json.load(file)
        file_content['num_questions'] = len(list_questions_data)
        file_content['test']['questions'] = list_questions_data
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(file_content, file, ensure_ascii=False, indent=4)

        form = Fabric(model).generate()
        return redirect('/account/profile')


class Register(View):
    def get(self, request: HttpRequest):
        form = UserCreationForm()
        is_authenticated = request.user.is_authenticated
        return render(request, 'register.html', {'form': form, 'is_authenticated': is_authenticated})

    def post(self, request: HttpRequest):
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
        return redirect('')

class Login(View):
    def get(self, request: HttpRequest):
        form = AuthenticationForm()
        is_authenticated = request.user.is_authenticated
        return render(request, 'login.html', {'form': form, 'is_authenticated': is_authenticated})

    def post(self, request: HttpRequest):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')


class Logout(View):
    def get(self, request: HttpRequest):
        if not request.user.is_authenticated:
            return redirect('/account/login')
        logout(request)
        return redirect('/')

@sync_to_async
def get_user_files(user: User):
    print(user)
    user_files = UserFile.objects.filter(user=user).all()
    print(user_files)
    files = []
    for user_file in user_files:
        files.append(Test.objects.filter(file=user_file.file.id).first())
    return user_files


@sync_to_async
def del_file(file_id: str):
    file_id = str(file_id).replace("-", "")
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
    def __delete_file(file_path: str):
        os.remove(file_path)
    
    file = UserFile.objects.filter(file = file_id)
    test = Test.objects.filter(id=file_id).first()
    print('=-====> test', test)
    __delete_file(os.path.join(upload_dir, 'json', f'{file_id}.json'))
    __delete_file(os.path.join(upload_dir, 'pdf', f'{file_id}.pdf'))
    __delete_file(os.path.join(upload_dir, 'xml', f'{file_id}.xml'))
    __delete_file(test.file.path)
    file.delete()
    test.delete()

@sync_to_async
def path_files(models: List[Test]) -> Tuple[str, str]:
    file_path = []
    for file in models:
        xml_model = XML(file.file).generate()
        pdf_model = PDF(file.file).generate()

        if not pdf_model or not xml_model:
            continue
        file_path.append(file)
    return file_path


class Profile(View):
    async def get(self, request: HttpRequest):
        is_authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
        if not is_authenticated:
            return redirect('/account/login')
        source_files = await get_user_files(request.user)
        files = await path_files(source_files)
        return render(request, 'profile.html', context={'files': files, 'is_authenticated': is_authenticated})
    
    @csrf_exempt
    async def post(self, request: HttpRequest):
        data = json.loads(request.body)
        print(data)
        await del_file(data["fileId"])
        return JsonResponse({
            'ok': True,
            'status': 'success',
            'message': 'File deleted successfully'
        })