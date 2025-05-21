import datetime
import os
import pprint
from typing import List
from django import forms
from django.http import HttpResponse
from docx import Document
import fitz

from django.conf import settings
from .models import Test

import httpx
import json


from django import forms
from django.http import HttpResponse
from .models import Test
import json

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

import xml.etree.ElementTree as ET

class Fabric:
    def __init__(self, model: Test):
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'json')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, f'{str(model.id).replace("-", "")}.json')
        self.file_path = file_path
        self.model = model
        self.option = (
            ('multiple_choice', 'Множественный выбор'),
            ('radio_choice', 'Одиночный выбор')
        )
        self.option_difficulty = (
            ("light", "Легкий"),
            ("medium", "Средний"),
            ("hard", "Тяжелый")
        )

    def __fields(self, data, form):
        for index, value in enumerate(data['options']):
            form.fields[f"{data['id']}_{index}"] = forms.CharField(label=f"Ответ {index+1}", initial=value, widget=forms.Textarea(attrs={'class': 'auto-resize'}))
        return form

    def generate(self):
        read_data = self.__read()
        if not read_data:
            return None

        data = self.__json_load(read_data)
        form = self.Form()
        for index, question in enumerate(data['test']['questions']):
            form.fields[question['id']] = forms.CharField(label=f"Вопрос №{index + 1}", initial=question["question"], widget=forms.Textarea(attrs={'class': 'auto-resize question'}))
            form = self.__fields(question, form)
            form.fields[f"{question['id']}_right"] = forms.CharField(label="Верный ответ", initial=question['right'], widget=forms.Textarea(attrs={'class': 'auto-resize'}))
            form.fields[f"{question['id']}_hint"] = forms.CharField(label="Подсказка", initial=question['hint'], widget=forms.Textarea(attrs={'class': 'auto-resize'}))
            form.fields[f"{question['id']}_explanation"] = forms.CharField(label="Объяснение", initial=question['explanation'], widget=forms.Textarea(attrs={'class': 'auto-resize'}))
            form.fields[f"{question['id']}_difficulty"] = forms.ChoiceField(
                choices=self.option_difficulty,
                label='Выберете сложность вопроса:',
                initial=question['difficulty'],
                widget=forms.Select(attrs={'class': 'my-select-class'})
            )

        return form

    def __json_load(self, read_data: str) -> dict:
        return json.loads(read_data)

    def __read(self) -> str:
        try:
            with open(self.file_path, 'r', encoding='UTF-8') as f:
                return f.read()
        except Exception as e:
            return None

    class Form(forms.Form):
        pass


OPENAI_KEY = "sk-Idooge0og0Dflfh_wxscnw"
BASE_URL = "https://hubai.loe.gg/v1"
MODEL = "deepseek-chat-fast"

custom_timeout = httpx.Timeout(
        connect=10.0,
        read=180.0,
        write=30.0,
        pool=5.0
    )

async def ask_openai(content: str) -> str:
    """
    Отправляет один chat‑запрос и возвращает ответ модели.
    """
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [
            {"role": "user", "content": content}
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=custom_timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        print(r.text)                  
        data = r.json()
        return data["choices"][0]["message"]["content"]


async def ask_mistral(content: str) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 1RjvjtgXwhXKqKR1WqKrqFUtuOoeaU9f"
    }
    data = {
        # "presence_penalty": 1,
        # "frequency_penalty": 1,
        # "temperature": 0.9,
        "model": "pixtral-12b-2409",
        "messages": [
            {"role": "user", "content": content}
        ]
    }

    async with httpx.AsyncClient(timeout=custom_timeout) as client:
        r = await client.post(url, json=data, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

class ReadFile:
    def read(self, test: Test):
        name = test.file.name
        suffix = name.split('.')[-1]
        if suffix in ['pdf', 'doc', 'docx', 'txt']:
            method = getattr(self, f"_read_{suffix}")
            text = method(test.file.path)
            return text
        return None
    
    def _read_docx(self, path):
        file = Document(path)
        text = " ".join([paragraph.text for paragraph in file.paragraphs])
        return text
    
    def _read_doc(self, path):
        pass

    def _read_pdf(self, path):
        file = fitz.open(path)
        text = " ".join([page.get_text() for page in file])
        return text

    def _read_txt(self, path):
        text = ""
        with open(path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text
    
class Prompt:
    def __init__(self, prompt: str, q_text_prompt: str, question_count: int, field_type: str, difficulty: str):
        self.prompt = prompt
        self.q_text_prompt = q_text_prompt
        self.question_count = question_count
        self.field_type = field_type
        self.difficulty = difficulty

    def get(self):
        created_at = datetime.datetime.now().isoformat()
        json_template = {
            "test": {
                "id": "test-001",
                "created_at": created_at,
                "num_questions": self.question_count,
                "difficulty": self.difficulty,
                "supported_languages": ["ru"],
                "options_per_question": 4,
                "detail_level": "basic",
                "output_format": "json",
                "questions": [
                    {
                        "id": "q-001",
                        "type": self.field_type,
                        "difficulty": "hard",
                        "question": "Какой протокол работает поверх TCP и предназначен для передачи веб-страниц?",
                        "options": ["HTTP", "UDP", "FTP", "ICMP"],
                        "right": "HTTP",
                        "hint": "Использует порт 80 по умолчанию.",
                        "explanation": "HTTP (HyperText Transfer Protocol) обеспечивает передачу гипертекста по TCP-соединению."
                    }
                ]
            }
        }
        
        # Преобразуем JSON-шаблон в строку
        json_str = json.dumps(json_template, ensure_ascii=False, indent=2)
        
        # Формируем промпт
        text = f"""
        Вы - ассистент, который генерирует ответы ТОЛЬКО в формате JSON.
        
        ВАЖНО: ВАШ ОТВЕТ ДОЛЖЕН СОДЕРЖАТЬ ТОЛЬКО ВАЛИДНЫЙ JSON БЕЗ ЛЮБОГО ОКРУЖАЮЩЕГО ТЕКСТА
        
        ИНСТРУКЦИИ:
        1. Создайте ровно {self.question_count} уникальных вопросов типа "{self.field_type}" сложности "{self.difficulty}"
        2. ID вопросов должны иметь последовательный формат: "q-001", "q-002", ..., "q-{str(self.question_count).zfill(3)}"
        3. Каждый вопрос должен иметь 4 варианта ответа, один верный ответ, подсказку и объяснение
        4. Тематика теста: {self.prompt}
        5. Дополнительные указания: {self.q_text_prompt}
        
        Шаблон ожидаемого формата JSON:
        ```
        {json_str}
        ```
        
        ВЕРНИТЕ ТОЛЬКО ВАЛИДНЫЙ JSON, СОДЕРЖАЩИЙ {self.question_count} ВОПРОСОВ. НЕ ДОБАВЛЯЙТЕ НИКАКИХ КОММЕНТАРИЕВ.
        """
        return text

pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
class PDF:
    def __init__(self, model: Test):
        json_upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'json')
        os.makedirs(json_upload_dir, exist_ok=True)

        json_file_path = os.path.join(json_upload_dir, f'{str(model.id).replace("-", "")}.json')
        self.json_file_path = json_file_path
        print('----------->', model.id)

        upload_dir_pdf = os.path.join(settings.MEDIA_ROOT, 'uploads', 'pdf')
        os.makedirs(upload_dir_pdf, exist_ok=True)

        pdf_file_path = os.path.join(upload_dir_pdf, f'{str(model.id).replace("-", "")}.pdf')
        self.pdf_file_path = pdf_file_path
        self.doc = SimpleDocTemplate(pdf_file_path, pagesize=letter)
        self.styles = getSampleStyleSheet()
        self.story = []
        self.right = []
        self.styles['Normal'].fontName = 'Arial'
        self.styles['Title'].fontName = 'Arial'
        self.styles['Title'].alignment = TA_LEFT
        self.name = model.name
        self.model = model


    def generate(self):
        try:
            json_data = self.__read_json(self.json_file_path)
            data = self.__json_load(json_data)
            self.__paragraph(f"<b>{self.name}</b>")
            self.story.append(Spacer(1, 24))
            for index, value in enumerate(data['test']['questions']):
                self.__paragraph(f"<b>{index+1}. {value['question']}</b>")
                self.__numeric_list(value["options"])
                self.story.append(Spacer(1, 24))
                self.__right_list(f"<b>{index+1}. {value['right']}</b>")
            
            self.story.append(PageBreak())
            self.story.append(self.__paragraph("Правильные ответы:"))
            for i in self.right:
                self.story.append(i)
            
            self.doc.build(self.story)
            return self.model
        except Exception:
            return None

    def __paragraph(self, text: str):
        self.story.append(Paragraph(text, self.styles["Title"]))

    def __numeric_list(self, data: list):
        items = [ListItem(Paragraph(i, self.styles["Normal"]), bulletType='1') for i in data]
        numbered_list = ListFlowable(
            items,
            bulletType='1',
            start='1',
            leftIndent=20,
            bulletFontName='Helvetica',
            bulletFontSize=10
        )
        self.story.append(numbered_list)

    def __right_list(self, text: str):
        self.right.append(Paragraph(text, self.styles["Normal"]))

    def __read_json(self, path):
        try:
            print('path =======>', path)
            with open(path, 'r', encoding='UTF-8') as f:
                return f.read()
        except Exception as e:
            return None

    def __json_load(self, read_data: str) -> dict:
        print("data = >", read_data)
        return json.loads(read_data)
    

class XML:
    def __init__(self, model: Test):
        json_upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'json')
        os.makedirs(json_upload_dir, exist_ok=True)

        json_file_path = os.path.join(json_upload_dir, f'{str(model.id).replace("-", "")}.json')
        self.json_file_path = json_file_path

        upload_dir_xml = os.path.join(settings.MEDIA_ROOT, 'uploads', 'xml')
        os.makedirs(upload_dir_xml, exist_ok=True)

        xml_file_path = os.path.join(upload_dir_xml, f'{str(model.id).replace("-", "")}.xml')
        self.xml_file_path = xml_file_path
        self.model = model

    def generate(self):
        try:
            json_data = self.__read_json(self.json_file_path)
            data = self.__json_load(json_data)

            quiz = ET.Element('quiz')
            for question in data['test']['questions']:
                question_element = ET.SubElement(quiz, 'question', type='multichoice')

                name = ET.SubElement(question_element, 'name')
                name_text = ET.SubElement(name, 'text')
                name_text.text = question['question']

                questiontext = ET.SubElement(question_element, 'questiontext', format='html')
                questiontext_text = ET.SubElement(questiontext, 'text')
                questiontext_text.text = f'<p>{question["question"]}</p>'

                for option in question['options']:
                    answer = ET.SubElement(question_element, 'answer', fraction='100' if option == question['right'] else '0')
                    answer_text = ET.SubElement(answer, 'text')
                    answer_text.text = option

            # Создаем XML-дерево и записываем его в файл
            tree = ET.ElementTree(quiz)
            tree.write(self.xml_file_path, encoding='utf-8', xml_declaration=True)
            return self.model
        except Exception:
            return None 

    def __read_json(self, path):
        try:
            with open(path, 'r', encoding='UTF-8') as f:
                return f.read()
        except Exception as e:
            return None

    def __json_load(self, read_data: str) -> dict:
        return json.loads(read_data)