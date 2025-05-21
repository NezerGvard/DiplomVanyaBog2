from django import forms
from .models import Test

class TestForm(forms.ModelForm):
    file = forms.FileField(
        label='JSON File',
        widget=forms.FileInput(attrs={'accept': '.docx, .doc, .pdf, .txt'}),
        required=False
    )

    question_count = forms.IntegerField(
        label="Количество вопросов",
        widget=forms.NumberInput(attrs={
            'min': 5,
            'max': 20,
            'step': 1,
            'value': 5,
        }),
        required=True
    )

    difficulty = forms.ChoiceField(
        label='Сложность',
        choices=[
            ("light", "Легкий"),
            ("medium", "Средний"),
            ("hard", "Тяжелый")
        ],
        widget=forms.Select(),
        required=True
    )


    class Meta:
        model = Test
        fields = ('file', 'name')
