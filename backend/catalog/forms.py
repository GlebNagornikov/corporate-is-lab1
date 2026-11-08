from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "text"]
        widgets = {
            "rating": forms.Select(choices=[(i, "★" * i) for i in range(5, 0, -1)]),
            "text": forms.Textarea(attrs={"rows": 3}),
        }
