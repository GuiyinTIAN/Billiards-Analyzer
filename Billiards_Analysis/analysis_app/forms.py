from django import forms
from .models import BilliardAnalysis

class BilliardImageForm(forms.ModelForm):
    class Meta:
        model = BilliardAnalysis
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'image': 'Select Billiards Image',
        }

