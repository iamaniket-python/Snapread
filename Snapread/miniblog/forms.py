from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile, Post, Comment


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model  = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-input'})

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email


class LoginForm(forms.Form):
    email    = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-input', 'placeholder': 'Enter your email'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input', 'placeholder': 'Enter your password'
    }))


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = Profile
        fields = ['bio', 'profile_image', 'website']
        widgets = {
            'bio':     forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'website': forms.URLInput(attrs={'class': 'form-input'}),
        }


class PostForm(forms.ModelForm):
    class Meta:
        model  = Post
        fields = ['title', 'content', 'category', 'tags', 'featured_image', 'status']
        widgets = {
            'title':    forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Post title...'}),
            'content':  forms.Textarea(attrs={'class': 'form-input editor-textarea', 'rows': 20, 'placeholder': 'Tell your story...'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'tags':     forms.SelectMultiple(attrs={'class': 'form-input'}),
            'status':   forms.Select(attrs={'class': 'form-input'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model  = Comment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Write a response...',
            }),
        }
        labels = {'comment': ''}